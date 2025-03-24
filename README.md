# South Dakota motor vehicle stats
Creating [a tidy CSV](south-dakota-motor-vehicle-stats.csv) of [motor vehicle registration stats](https://sddor.seamlessdocs.com/sc/statistics/) in South Dakota by county by year. Updated weekly.

PDF reports for each calendar year, downloaded from the Department of Revenue's website, are in `reports`, along with [a historical file](reports/south-dakota-motor-vehicle-stats-historical.pdf) with annual totals for the past couple of years for each county.

To combine them, the basic idea is to pull out annual totals from the historical file, then add in data from reports that aren't represented in the historical file.

### [`south-dakota-motor-vehicle-stats.csv`](south-dakota-motor-vehicle-stats.csv)
- `county`: County name
- `county_fips`: County FIPS code
- `year`: Registration year
- `registration_type`: The type of registration, e.g. truck, bus, etc. (but also "title")
- `total`: The total number of registrations of that type for the county for the year

### Running the Python script
[`update.py`](update.py) checks for new reports, downloads new ones (plus the current-year report, which is updated throughout the year with new monthly totals), extracts the data from each PDF and combines the data into a flat file, [`south-dakota-motor-vehicle-stats.csv`](south-dakota-motor-vehicle-stats.csv).
