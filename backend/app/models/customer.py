from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Customer(Base):
    """Customer register (Kundregister)"""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    # Customer details
    name = Column(String, nullable=False)
    org_number = Column(String(15), nullable=True)  # Optional for individuals
    contact_person = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # Address
    address = Column(String, nullable=True)
    postal_code = Column(String(10), nullable=True)
    city = Column(String, nullable=True)
    country = Column(String, default="Sverige", nullable=False)

    # Payment terms
    payment_terms_days = Column(Integer, default=30, nullable=False)  # Default 30 days

    # Status
    active = Column(Boolean, default=True, nullable=False)

    # Relationships
    company = relationship("Company")
    invoices = relationship("Invoice", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer {self.name}>"


class Supplier(Base):
    """Supplier register (Leverantörsregister)"""

    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    # Supplier details
    name = Column(String, nullable=False)
    org_number = Column(String(15), nullable=True)
    contact_person = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # Address
    address = Column(String, nullable=True)
    postal_code = Column(String(10), nullable=True)
    city = Column(String, nullable=True)
    country = Column(String, default="Sverige", nullable=False)

    # Payment terms
    payment_terms_days = Column(Integer, default=30, nullable=False)

    # Bank details
    bank_account = Column(String, nullable=True)  # Bankgiro or account number
    bank_name = Column(String, nullable=True)

    # Status
    active = Column(Boolean, default=True, nullable=False)

    # Relationships
    company = relationship("Company")
    supplier_invoices = relationship("SupplierInvoice", back_populates="supplier", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Supplier {self.name}>"
