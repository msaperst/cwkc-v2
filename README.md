# cwkc

Commonwealth Kiddish Cup

[Hosted online here](https://msaperst.github.io/cwkc-v2/)

## Workflow

1. Forms are filled out
2. Results populate into Google forms
3. GHA run on schedule to assemble data from multiple Google form into single `results.csv` file
4. `index.html` pulls data from `results.csv` file

## Dev

## Test

## CI

Everything runs in GHA on scheduled triggers. Step 3
is scheduled to run every 5 minutes, but can be triggered
manually for more frequent runs. In order to authenticate
with the spreadsheets, credentials have been saved into GHA
following [these instructions](https://docs.gspread.org/en/v6.1.3/oauth2.html#for-bots-using-service-account).

We're using a service bot for scraping this data, which is
`google-sheets-service-account@hillel-51aad.iam.gserviceaccount.com`