class SubmittedData:
    def __init__(self):
        self.hokies = 0
        self.hoos = 0


def get_alumni_gatherings(gc):
    """Gets the alumni gathering information

    All the data is in one spreadsheet, with the schools listed in Column C.
    We need to determine the correct school based on that column. Additionally,
    there needs to be at least 4 people attending the event, so we'll check the
    corresponding Column E to ensure we have enough people. Finally, we retrieve
    the images posted, which are stored in Column G
    """

    sh = gc.open_by_key('1EOURh5B5mKy0AjAgTKMObYtdmvZGI8txVC18DCmlA5o')
    rows = sh.sheet1.get_all_values()  # get all of our rows
    rows.pop(0)  # remove our header row

    data = SubmittedData()
    for row in rows:
        # this logic might need to be improved, as of now, we just ensure
        # that there are 4 names comma separated (3 commas for 4 names)
        number_of_people_in_attendance = row[4].count(',')
        enough_people = number_of_people_in_attendance >= 3

        if 'Brody' in row[2] and enough_people:
            data.hoos += 1
        if 'Tech' in row[2] and enough_people:
            data.hokies += 1

    # TODO - return the images and do something with them

    return data


def get_alumni_memories(gc):
    """Gets the alumni hillel memory information

    All the data is in one spreadsheet, with the schools listed in Column D.
    We need to determine the correct school based on that column. Additionally,
    you need to be a 'young alumni' which is indicated in corresponding Column E.
    Finally, we retrieve the testimonial and/or  video, which are stored in Column H
    """

    sh = gc.open_by_key('128regkVYg_RqRyZszxBHpIv1z7RkM0_HQlDBr58xkCc')
    rows = sh.sheet1.get_all_values()  # get all of our rows
    rows.pop(0)  # remove our header row

    data = SubmittedData()
    for row in rows:
        print(row)
        young_alumni = row[4] == 'Yes'

        if 'University' in row[3] and young_alumni:
            data.hoos += 1
        if 'Tech' in row[3] and young_alumni:
            data.hokies += 1

    # TODO - return the testimonial and do something with them

    return data
