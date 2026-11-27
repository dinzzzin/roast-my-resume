"""Expected: nesting_depth
Trap: a method (needs self), so the equivalence check should report "not testable"."""


class Inventory:
    def __init__(self):
        self.stock = {}

    def restock(self, deliveries):
        added = 0
        for delivery in deliveries:
            if delivery:
                for sku, qty in delivery.items():
                    if qty > 0:
                        if sku in self.stock:
                            self.stock[sku] += qty
                        else:
                            self.stock[sku] = qty
                        added += qty
        return added
