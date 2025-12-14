from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, get_user_company_ids, verify_company_access
from app.models.customer import Customer
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter()


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer: CustomerCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Create a new customer"""
    # Verify user has access to this company
    company_ids = get_user_company_ids(current_user, db)
    if customer.company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"You don't have access to company {customer.company_id}"
        )

    db_customer = Customer(**customer.model_dump())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer


@router.get("/", response_model=list[CustomerResponse])
def list_customers(
    company_id: int = Query(..., description="Company ID"),
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _: None = Depends(verify_company_access),
):
    """List all customers for a company"""
    query = db.query(Customer).filter(Customer.company_id == company_id)

    if active_only:
        query = query.filter(Customer.active.is_(True))

    customers = query.order_by(Customer.name).all()
    return customers


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Get a specific customer"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer {customer_id} not found")

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if customer.company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this customer")

    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    customer_update: CustomerUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update a customer"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer {customer_id} not found")

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if customer.company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this customer")

    update_data = customer_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Delete a customer"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer {customer_id} not found")

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if customer.company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this customer")

    db.delete(customer)
    db.commit()
    return None
