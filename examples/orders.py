"""Demo input only. It is never executed by the labeler."""


def process_pending_orders(orders):
    """Validate pending orders and prepare them for dispatch."""
    valid_orders = [order for order in orders if order.is_valid()]
    return [order.prepare_dispatch() for order in valid_orders]
