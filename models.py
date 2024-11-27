from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class QA(Base):
    __tablename__ = 'qa'
    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

engine = create_engine('sqlite:///qa_database.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()