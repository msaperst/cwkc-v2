# cwkc

Commonwealth Kiddish Cup

[Hosted online here](https://msaperst.github.io/cwkc-v2/)

## Workflow

1. Forms are filled out
2. Results populate into Google Sheets
3. When Google Sheets changes, a GHA is triggered to
   scrape data into a single `results.csv` file
4. `index.html` pulls data from `results.csv` file

## Dev

## Test

## CI

In order to trigger the changes, each of the Google
Sheets that is capturing our data has a custom trigger
function written for it. When data changes, it triggers
a GitHub Action to scrape and update data. If needed, it
can be triggered manually for more frequent runs. In
order to authenticate with the spreadsheets, credentials
have been saved into GHA following
[these instructions](https://docs.gspread.org/en/v6.1.3/oauth2.html#for-bots-using-service-account).

We're using a service bot for scraping this data, which is
`google-sheets-service-account@hillel-51aad.iam.gserviceaccount.com`