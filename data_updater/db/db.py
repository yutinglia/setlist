import sqlalchemy as db


class Database:
    def __init__(self, db_url):
        self.engine = db.create_engine(db_url)
        self.connection = self.engine.connect()
        self.metadata = db.MetaData()

    def create_table(self, table_name, columns):
        table = db.Table(table_name, self.metadata, *columns)
        self.metadata.create_all(self.engine)
        return table

    def insert_data(self, table, data):
        insert_query = table.insert().values(data)
        self.connection.execute(insert_query)

    def fetch_data(self, table, conditions=None):
        select_query = db.select([table])
        if conditions:
            select_query = select_query.where(conditions)
        result = self.connection.execute(select_query)
        return result.fetchall()

    def close(self):
        self.connection.close()
        self.engine.dispose()
