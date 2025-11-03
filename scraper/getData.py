import gspread
import pandas

from getSubmittedData import get_alumni_gatherings, get_alumni_memories, get_mitzvah_memories

# set up our connection to google spreadsheets
gc = gspread.service_account(filename='spreadsheet_credentials.json')
# open up our csv file
df = pandas.read_csv('../public/assets/csv/results.csv')

# update data from our alumni gatherings
alumni_gatherings_score = get_alumni_gatherings(gc)
df.loc[0, 'alumniGatheringsUVA'] = alumni_gatherings_score.hoos
df.loc[0, 'alumniGatheringsTech'] = alumni_gatherings_score.hokies

# update data from our alumni memories
mitzvah_memories_score = get_mitzvah_memories(gc)
df.loc[0, 'alumniMemoriesUVA'] = mitzvah_memories_score.hoos
df.loc[0, 'alumniMemoriesTech'] = mitzvah_memories_score.hokies

# write new details into our file
df.to_csv('../public/assets/csv/results.csv', index=False)
