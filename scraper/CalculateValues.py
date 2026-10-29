from typing import Dict, Any

import gspread
import pandas as pd

PHONE_NUMBER = 'phone number'
TOTAL_AMOUNT = 'total amount'
RECURRING_PAYMENT = 'recurring payment'


class CalculateValues:
    """
    Pulls normalized donation data from Google Sheets and calculates metrics per school.
    """

    FAMILY_STATUSES = ['Current Parent', 'Current Grandparent', 'Parent of Alumni', 'Grandparent of Alumni']
    GRANDPARENT_STATUS = ['Current Grandparent']

    def __init__(self, spreadsheet_key: str, worksheet_name: str = "entries",
                 creds_file: str = "spreadsheet_credentials.json"):
        self.spreadsheet_key = spreadsheet_key
        self.worksheet_name = worksheet_name
        self.creds_file = creds_file
        self.df = self._load_data()

    def _load_data(self) -> pd.DataFrame:
        """Pull normalized data from Google Sheets into a DataFrame."""
        gc = gspread.service_account(filename=self.creds_file)
        sh = gc.open_by_key(self.spreadsheet_key)
        ws = sh.worksheet(self.worksheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)

        # If there are no rows, create an empty DataFrame with all expected columns
        expected_columns = [
            'source', TOTAL_AMOUNT, RECURRING_PAYMENT, 'first name', 'last name',
            PHONE_NUMBER, 'anonymous donation', 'first time giver',
            'graduation year', 'status', 'work referral'
        ]
        if df.empty:
            df = pd.DataFrame(columns=expected_columns)

        # Normalize columns
        df['source'] = df['source'].str.lower()
        df[TOTAL_AMOUNT] = pd.to_numeric(df[TOTAL_AMOUNT], errors='coerce').fillna(0)
        df[RECURRING_PAYMENT] = df[RECURRING_PAYMENT].str.lower().map({'true': True, 'false': False})

        return df

    # =================== Public Interface ===================
    def calculate_all(self) -> Dict[str, Dict[str, Any]]:
        """Compute all metrics for UVA and VT."""
        return {
            'uva': self._calculate_school_metrics('uva'),
            'vt': self._calculate_school_metrics('vt')
        }

    # =================== Internal Helpers ===================
    def _calculate_school_metrics(self, school_prefix: str) -> Dict[str, Any]:
        """Compute all metrics for a given school prefix ('uva' or 'vt')."""
        school_df = self.df[self.df['source'].str.startswith(school_prefix)]

        # Normalize status field to be list-like
        school_df = school_df.copy()
        school_df['status_list'] = school_df['status'].fillna('').apply(
            lambda x: [s.strip() for s in str(x).split(',') if s.strip()]
        )

        # If no rows, return zeros for all metrics
        if school_df.empty:
            zero_metrics = {
                "total_amount": 0,
                "most_individual_donors": 0,
                "donor_names": "",
                "most_first_time_donors": 0,
                "most_donors_class_2026": 0,
                "most_gifts_over_1000": 0,
                "most_alum_monthly_10_plus": 0,
                "most_alum_work_matched": 0,
                "most_money_families": 0,
                "most_money_grandparents_current_students": 0
            }
            return zero_metrics

        # Otherwise, calculate metrics normally
        return {
            "total_amount": self._total_raised(school_df),
            "most_individual_donors": self._unique_donors_count(school_df),
            "donor_names": self._donor_names(school_df),
            "most_first_time_donors": self._first_time_donors_count(school_df),
            "most_donors_class_2026": self._class_year_donors(school_df, 2026),
            "most_gifts_over_1000": self._gifts_over_1000_count(school_df),
            "most_alum_monthly_10_plus": self._alumni_monthly_10_plus(school_df),
            "most_alum_work_matched": self._alumni_work_matched(school_df),
            "most_money_families": self._money_by_statuses(school_df, self.FAMILY_STATUSES),
            "most_money_grandparents_current_students": self._money_by_statuses(school_df, self.GRANDPARENT_STATUS)
        }

    # =================== Individual Metric Functions ===================
    def _total_raised(self, df: pd.DataFrame) -> float:
        return df.apply(lambda r: r[TOTAL_AMOUNT] * 12 if r[RECURRING_PAYMENT] else r[TOTAL_AMOUNT], axis=1).sum()

    def _unique_donors_count(self, df: pd.DataFrame) -> int:
        return df[[PHONE_NUMBER]].drop_duplicates().shape[0]

    def _donor_names(self, df: pd.DataFrame) -> str:
        # Only include donors who are not anonymous
        filtered = df[df['anonymous donation'].str.lower() != 'true']
        unique = filtered[[PHONE_NUMBER, 'first name', 'last name']].drop_duplicates()
        return ", ".join(unique.apply(lambda x: f"{x['first name']} {x['last name']}".strip(), axis=1))

    def _first_time_donors_count(self, df: pd.DataFrame) -> int:
        # count unique donors who are first-time givers
        ft_df = df[df['first time giver'].str.lower() == 'true']
        return ft_df[[PHONE_NUMBER]].drop_duplicates().shape[0]

    def _class_year_donors(self, df: pd.DataFrame, year: int) -> int:
        """Count unique alumni from the specified graduating class.

        Parents' or grandparents' *associated student's* year is not the
        donor's own graduation year; they cannot earn this category.
        The final LGL adapter must identify the donor's alumni year.
        """
        alumni = df[df['status_list'].apply(lambda statuses: 'Alumni' in statuses)]
        graduation_years = pd.to_numeric(alumni['graduation year'], errors='coerce')
        return alumni.loc[graduation_years.eq(year), PHONE_NUMBER].nunique()

    def _gifts_over_1000_count(self, df: pd.DataFrame) -> int:
        amounts = df.apply(lambda r: r[TOTAL_AMOUNT] * 12 if r[RECURRING_PAYMENT] else r[TOTAL_AMOUNT], axis=1)
        return amounts[amounts >= 1000].count()

    def _alumni_monthly_10_plus(self, df: pd.DataFrame) -> int:
        return df[df['status_list'].apply(lambda lst: 'Alumni' in lst) & (df[RECURRING_PAYMENT]) & (
                df[TOTAL_AMOUNT] >= 10)].shape[0]

    def _alumni_work_matched(self, df: pd.DataFrame) -> int:
        return \
            df[df['status_list'].apply(lambda lst: 'Alumni' in lst) & (
                    df['work referral'].str.lower() == 'true')].shape[0]

    def _money_by_statuses(self, df: pd.DataFrame, statuses: list) -> float:
        filtered = df[df['status_list'].apply(lambda lst: any(s in lst for s in statuses))]
        return filtered.apply(lambda r: r[TOTAL_AMOUNT] * 12 if r[RECURRING_PAYMENT] else r[TOTAL_AMOUNT],
                              axis=1).sum()
