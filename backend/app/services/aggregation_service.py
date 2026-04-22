
import pandas as pd

class AggregationService:
    def aggregate(self, df, column, operation):
        if operation == "sum":
            return df[column].sum()
        elif operation == "avg":
            return df[column].mean()
        elif operation == "count":
            return df[column].count()
        return None
