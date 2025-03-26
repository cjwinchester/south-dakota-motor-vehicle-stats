import os
import csv
import time
import logging
from datetime import date
from pathlib import Path
from typing import Self

import requests
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd


logging.basicConfig(
    level=logging.INFO,
    format='{asctime} - {levelname} - {message}\n',
    style='{'
)

pd.options.mode.chained_assignment = None

DIR_REPORTS = Path('reports')
FILEPATH_STUB = 'south-dakota-motor-vehicle-stats'
FILEPATH_OUT_CSV = Path(f'{FILEPATH_STUB}.csv')

REQ_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:129.0) Gecko/20100101 Firefox/129.0'
}

THIS_YEAR = date.today().year

HEADERS = [
    'county',
    'county_fips',
    'year',
    'passenger_low_speed',
    'pickup_suv_van',
    'truck',
    'bus',
    'trailer',
    'motorcycle',
    'off_road',
    'recreational',
    'snowmobile',
    'boat',
    'commercial_plate',
    'gross_vehicle_weight',
    'irp_with_prorate_plate',
    'electric',
    'titles'
]


def fetch_report_urls() -> dict:
    """Fetch a list of URLs pointing to PDFs of motor vehicle registration stats in S.D.

    Returns:
        Dictionary with the year as key, report URL as value.
    """

    url = 'https://sddor.seamlessdocs.com/sc/api/folders/v2/statistics/active-details'

    r = requests.get(
        url,
        headers=REQ_HEADERS
    )

    r.raise_for_status()

    time.sleep(1)

    html = r.json()['welcomeLetter']['content']
    soup = BeautifulSoup(html, 'html.parser')

    mv_links = soup.find('h1', string='Motor Vehicle').find_next_sibling('ul').find_all('li')

    reports = {}

    for link in mv_links:
        label = link.text.strip().lower()

        if 'historical' in label:
            year = 'historical'

        if label.startswith('cy'):
            year = int(f'20{label.split()[0][-2:]}')

        reports[year] = link.find('a').get('href')

    return reports


def get_sd_fips_lookup() -> dict:
    """Get a lookup of county name -> FIPS code for S.D."""

    df = pd.read_csv(
        'https://raw.githubusercontent.com/cjwinchester/sd-voter-registration-data/main/us-county-fips.csv',
        dtype={
            'state_fips': str,
            'county_fips': str
        }
    )

    sd = df[df['state_abbr'] == 'SD']
    sd['fips'] = sd['state_fips'] + sd['county_fips']
    sd['county_name'] = sd['county_name'].str.replace(' County', '')

    d = {x[1].get('county_name'): x[1].get('fips') for x in sd.iterrows()}

    d['Oglala Lakota'] = '46113'

    return d


class Report:
    """A South Dakota motor vehicle registration stats report."""

    def __init__(
        self,
        year: int,
        url: str,
        fips_lookup: dict = {}
    ) -> None:

        self.year = year
        self.url = url
        self.filepath = DIR_REPORTS / f'{FILEPATH_STUB}-{year}.pdf'
        self.lookup = fips_lookup

    def download_report(self) -> Self:
        """Conditionally download the report."""
        
        if self.filepath.exists() and self.year != THIS_YEAR:
            return self

        with requests.get(
            self.url,
            headers=REQ_HEADERS,
            stream=True
        ) as r:
            r.raise_for_status()
            time.sleep(1)

            with open(self.filepath, 'wb') as f:
                for chunk in r.iter_content():
                    f.write(chunk)

            logging.info(f'Wrote {self.filepath}')

        return self


    def extract_data(self) -> Self:
        """Extract the PDF data.

        Sets:
            self.county
            self.county_fips
            self.data
            self.df
        """
        data = []

        with pdfplumber.open(self.filepath) as pdf:
            pages_data = pdf.pages[3:]
    
            for page in pages_data:
        
                words = page.extract_words()
        
                if words[0].get('text').lower() != 'titles':
                    continue
        
                county = [words[3].get('text')]

                for word in words[4:]:
                    if word.get('text').lower() == 'vehicle':
                        break
                    else:
                        county.append(word.get('text'))

                county = ' '.join(county)
                self.county = county

                county_fips = self.lookup.get(county, '')
                self.county_fips = county_fips

                table = page.extract_table()

                if self.year == 'historical':
                    for line in table:
                        line = [x for x in line if x]

                        if 'CY' not in line[0]:
                            continue

                        line = [int(x.replace('CY ', '').replace(',', '')) for x in line]

                        year = line[0]

                        # fix one line that's off
                        if county == 'Ziebach' and year == 2015:
                            line.insert(4, 0)
        
                        line_data = [county, county_fips] + line

                        data.append(
                            dict(zip(HEADERS, line_data))
                        )
                else:
                    total_line = [x for x in table if x[0] == 'Total'][0]

                    total_line = [int(x.replace(',', '')) for x in total_line if x and x != 'Total']
        
                    page_data = [county, county_fips, self.year] + total_line

                    data.append(
                        dict(zip(HEADERS, page_data))
                    )
    
        self.data = data

        logging.info(f'Scraped {len(data)} records from {self.year} report.')

        self.df = pd.melt(
            pd.DataFrame(data),
            id_vars=['county', 'county_fips', 'year'],
            var_name='registration_type',
            value_name='total'
        )

        return self

    def __str__(self):
        return f'{self.year}'


def scrape_data() -> list[Report]:
    """Download new S.D. motor vehicle stats reports and scrape
    the data into a CSV.

    Returns:
        reports_processed (list): A list of processed Report objects.
    """

    reports_processed = []

    reports = fetch_report_urls()
    fips_lookup = get_sd_fips_lookup()

    df = pd.DataFrame()

    for year in reports:
        url = reports[year]
        report = Report(
            year,
            url,
            fips_lookup=fips_lookup
        )

        report.download_report()
        report.extract_data()

        df = pd.concat([df, report.df])

        reports_processed.append(report)

    df.sort_values(
        ['county', 'year', 'registration_type'],
        ascending=[True, False, True],
        inplace=True
    )

    df.drop_duplicates(inplace=True)

    df.to_csv(
        FILEPATH_OUT_CSV,
        index=False
    )

    logging.info(f'Wrote {len(df):,} records to {FILEPATH_OUT_CSV}')

    return reports_processed


if __name__ == '__main__':
    scrape_data()
