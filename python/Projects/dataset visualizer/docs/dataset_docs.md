# Superstore Sales Dataset Documentation

## Overview

This dataset tracks retail orders for a fictional superstore chain across
three product categories: Furniture, Office Supplies, and Technology.
Each row represents one line item within an order. A single order can
contain multiple line items, so `order_id` is not unique per row.

Note: the Columns section below documents the primary business columns
only. A given upload may contain additional columns not listed here
(e.g. product name/ID, customer name, city, state, ship mode) - use the
list_dataset_columns tool to see the exact columns present in the
currently uploaded file.

## Columns

### order_id
Unique identifier for the order this line item belongs to. Format:
`US-YYYY-NNNNNNN`. Multiple rows can share the same order_id.

### order_date
The date the customer placed the order. Used for all time-series and
trend questions ("sales over time", "monthly revenue").

### ship_date
The date the order was shipped. `ship_date - order_date` gives fulfillment
time in days. Anything over 7 days is considered a delayed shipment
per company policy.

### category
One of: Furniture, Office Supplies, Technology. This is the top-level
product grouping — use this column, not `sub_category`, when a question
asks about broad product performance.

### sub_category
Finer-grained product type within a category (e.g. Chairs, Binders,
Phones). Use this for detailed product-mix questions.

### sales
Revenue in USD for this line item, before discount is subtracted, i.e.
this is gross revenue. To get net revenue, compute `sales * (1 - discount)`.

### quantity
Number of units in this line item.

### discount
Discount applied to this line item, as a decimal fraction (0.2 = 20% off).

### profit
Profit in USD for this line item. Can be negative — some line items,
particularly deeply discounted Furniture items, sell at a loss. Any
"most/least profitable" question should sort on this column.

### region
One of: East, West, Central, South. Aggregate sales/profit by this
column for regional performance questions.

## Business rules and definitions

### "Revenue" vs "sales"
When a question asks about "revenue" without qualification, treat it as
equivalent to the `sales` column (gross), not net-of-discount, unless the
question explicitly says "net revenue" or "after discount".

### Profit margin
Defined as `profit / sales`. Not stored directly — must be computed.

### Delayed shipment
An order is considered delayed if `ship_date - order_date > 7` days.
This is a company-defined threshold, not an industry standard — always
apply it when asked about shipping performance.

### Loss-making line items
Any row where `profit < 0`. These are common in Furniture due to
aggressive discounting and should not be treated as data errors.