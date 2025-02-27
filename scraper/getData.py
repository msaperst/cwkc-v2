import gspread
import pandas

from scraper.getSubmittedData import get_alumni_gatherings, get_alumni_memories

# set up our connection to google spreadsheets
gc = gspread.service_account(filename='spreadsheet_credentials.json')
# open up our csv file
df = pandas.read_csv('../public/assets/csv/results.csv')

# update data from our alumni gatherings
alumni_gatherings_score = get_alumni_gatherings(gc)
df.loc[0, 'alumniGatheringsUVA'] = alumni_gatherings_score.hoos
df.loc[0, 'alumniGatheringsTech'] = alumni_gatherings_score.hokies

# update data from our alumni memories
alumni_memories_score = get_alumni_memories(gc)
df.loc[0, 'alumniMemoriesUVA'] = alumni_memories_score.hoos
df.loc[0, 'alumniMemoriesTech'] = alumni_memories_score.hokies

# write new details into our file
df.to_csv('../public/assets/csv/results.csv', index=False)
