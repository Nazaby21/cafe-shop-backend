from sqlalchemy.orm import Session

from app.models.stock_movement import StockMovement


def create_movement(db: Session, movement: StockMovement, commit: bool = True) -> StockMovement:
    db.add(movement)
    if commit:
        db.commit()
        db.refresh(movement)
    else:
        db.flush()
    return movement


def get_movements_for_product(db: Session, product_id: int, skip: int = 0, limit: int = 20):
    return (
        db.query(StockMovement)
        .filter(StockMovement.product_id == product_id)
        .order_by(StockMovement.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
