from sqlalchemy import Column, Date, Integer, MetaData, Numeric, String
from sqlalchemy.orm import declarative_base

meta = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})

Base = declarative_base(metadata=meta)


class Clients(Base):
    __tablename__ = 'Clients'
    __table_args__ = {'schema': 'store'}
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)
    address = Column(String(255), nullable=True)
    zip_code = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)
    date_of_birth = Column(Date, nullable=True)


class Products(Base):
    __tablename__ = 'Products'
    __table_args__ = {'schema': 'store'}
    id = Column(String(8), primary_key=True)
    name = Column(String(255), nullable=False)
    category_id = Column(Integer, nullable=False)
    description = Column(String(255), nullable=True)
    unit_price = Column(Numeric(10, 2), nullable=False)
    units_in_package = Column(Integer, nullable=True)
    package_weight = Column(Numeric(13, 3), nullable=True)
    manufacturer = Column(String(255), nullable=True)


class ProductWeekly(Base):
    __tablename__ = 'ProductWeekly'
    __table_args__ = {'schema': 'report'}
    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    week = Column(Integer, nullable=True)
    product_id = Column(Integer, nullable=True)
    sold_units = Column(Integer, nullable=True)
    sold_total_price = Column(Numeric(10, 2), nullable=True)
