"""Tiny in-memory inventory used to demo docgen."""

from dataclasses import dataclass, field


@dataclass
class Item:
    sku: str
    name: str
    quantity: int = 0
    price_cents: int = 0


@dataclass
class Inventory:
    items: dict[str, Item] = field(default_factory=dict)

    def add(self, item: Item) -> None:
        if item.sku in self.items:
            self.items[item.sku].quantity += item.quantity
        else:
            self.items[item.sku] = item

    def remove(self, sku: str, quantity: int) -> Item:
        item = self.items[sku]
        if quantity > item.quantity:
            raise ValueError(f"only {item.quantity} of {sku} in stock")
        item.quantity -= quantity
        return item

    def total_value_cents(self) -> int:
        return sum(i.quantity * i.price_cents for i in self.items.values())
