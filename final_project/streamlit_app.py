from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

import data_store


PUMP_COST = 0.10
MAX_PUMPS = 10


@dataclass(frozen=True)
class CartItem:
    drink: str
    size: str
    milk: str
    flavor: str
    pumps: int
    quantity: int
    base_price: float
    pump_price: float
    total_price: float


DELIVERY_SAVED = "Use employee record (office/extension)"
DELIVERY_OVERRIDE = "Deliver to a different office/extension for this order"


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _get_menu_lists(menu: dict[str, list[Any]]) -> tuple[list[str], list[str], list[str], list[str], list[float]]:
    coffees = [str(x) for x in menu.get("COFFEE", [])]
    sizes = [str(x) for x in menu.get("SIZES", [])]
    milks = [str(x) for x in menu.get("MILK", [])]
    flavors = [str(x) for x in menu.get("FLAVORS", [])]
    prices = [_as_float(x) for x in menu.get("PRICES", [])]
    return coffees, sizes, milks, flavors, prices


def _item_prices(size_index: int, prices: list[float], pumps: int, quantity: int) -> tuple[float, float, float]:
    base = prices[size_index] if 0 <= size_index < len(prices) else 0.0
    pump_price = float(pumps) * PUMP_COST
    total = (base + pump_price) * float(quantity)
    return float(base), float(pump_price), float(total)


def _ensure_state() -> None:
    if "employee_id" not in st.session_state:
        st.session_state.employee_id = None
    if "employee_confirmed" not in st.session_state:
        st.session_state.employee_confirmed = False
    if "cart" not in st.session_state:
        st.session_state.cart = []
    if "delivery_mode" not in st.session_state:
        st.session_state.delivery_mode = DELIVERY_SAVED
    if "delivery_office_override" not in st.session_state:
        st.session_state.delivery_office_override = ""
    if "delivery_extension_override" not in st.session_state:
        st.session_state.delivery_extension_override = ""
    if "order_confirming" not in st.session_state:
        st.session_state.order_confirming = False
    if "delivery_notes" not in st.session_state:
        st.session_state.delivery_notes = ""
    if "last_saved_order_id" not in st.session_state:
        st.session_state.last_saved_order_id = None
    if "last_receipt_text" not in st.session_state:
        st.session_state.last_receipt_text = None
    if "last_receipt_filename" not in st.session_state:
        st.session_state.last_receipt_filename = None


def _reset_employee_state() -> None:
    st.session_state.employee_id = None
    st.session_state.employee_confirmed = False
    st.session_state.cart = []
    st.session_state.delivery_mode = DELIVERY_SAVED
    st.session_state.delivery_office_override = ""
    st.session_state.delivery_extension_override = ""
    st.session_state.delivery_notes = ""
    st.session_state.order_confirming = False


def _set_current_employee(employee_id: int) -> None:
    st.session_state.employee_id = employee_id
    st.session_state.employee_confirmed = True


def _employee_display(employee_id: int) -> dict[str, str]:
    employees = data_store.load_employees()
    record = employees.get(str(employee_id), {}) if isinstance(employees, dict) else {}
    f_name = str(record.get("f_name", "")).strip()
    l_name = str(record.get("l_name", "")).strip()
    name = f"{f_name} {l_name}".strip()
    office = str(record.get("office", "")).strip()
    extension = str(record.get("extension", "")).strip()
    allergies = str(record.get("allergies", "")).strip()
    return {"name": name, "office": office, "extension": extension, "allergies": allergies}


def _cart_item_from_selection(
    drink: str,
    size: str,
    milk: str,
    flavor: str,
    pumps: int,
    quantity: int,
    sizes: list[str],
    prices: list[float],
) -> CartItem:
    size_index = sizes.index(size) if size in sizes else 0
    base_price, pump_price, total_price = _item_prices(size_index, prices, int(pumps), int(quantity))
    return CartItem(
        drink=drink,
        size=size,
        milk=milk,
        flavor=flavor,
        pumps=int(pumps),
        quantity=int(quantity),
        base_price=base_price,
        pump_price=pump_price,
        total_price=total_price,
    )


def _validate_delivery(office: str, extension: str) -> tuple[bool, str]:
    office = str(office or "").strip()
    extension = str(extension or "").strip()
    if not office:
        return False, "Office is required for internal delivery."
    if extension and (not extension.isdigit() or not (2 <= len(extension) <= 6)):
        return False, "Extension must be 2–6 digits (or leave blank)."
    return True, ""


def employees_tab() -> None:
    st.header("Employees")

    employees = data_store.load_employees()

    with st.form("employee_lookup"):
        employee_id_text = st.text_input("Employee number", value="")
        submitted = st.form_submit_button("Find / Create")

    if submitted:
        previous_employee_id = st.session_state.employee_id
        try:
            employee_id = int(employee_id_text.strip())
        except Exception:
            st.error("Employee number must be a whole number.")
            return

        st.session_state.employee_id = employee_id
        st.session_state.employee_confirmed = False
        if previous_employee_id != employee_id:
            st.session_state.cart = []
            st.session_state.delivery_mode = DELIVERY_SAVED
            st.session_state.delivery_office_override = ""
            st.session_state.delivery_extension_override = ""
            st.session_state.delivery_notes = ""
            st.session_state.order_confirming = False

    employee_id = st.session_state.employee_id
    if employee_id is None:
        st.info("Enter an employee number to get started.")
        return

    employee_key = str(employee_id)
    existing = employees.get(employee_key)

    if existing is None:
        st.subheader(f"New employee #{employee_id}")
        with st.form("new_employee"):
            f_name = st.text_input("First name")
            l_name = st.text_input("Last name")
            office = st.text_input("Office")
            extension = st.text_input("Extension")
            allergies = st.text_input("Allergies (comma-separated)", value="")
            save_new = st.form_submit_button("Save employee")

        if save_new:
            employees[employee_key] = {
                "f_name": f_name.strip(),
                "l_name": l_name.strip(),
                "office": office.strip(),
                "extension": extension.strip(),
                "allergies": allergies.strip(),
            }
            data_store.save_employees(employees)
            _set_current_employee(employee_id)
            st.success("Employee saved and selected.")
        return

    st.subheader(f"Employee #{employee_id}")
    st.write("Confirm the information on file.")

    with st.form("confirm_employee"):
        f_name = st.text_input("First name", value=existing.get("f_name", ""))
        l_name = st.text_input("Last name", value=existing.get("l_name", ""))
        office = st.text_input("Office", value=existing.get("office", ""))
        extension = st.text_input("Extension", value=existing.get("extension", ""))
        allergies = st.text_input("Allergies (comma-separated)", value=existing.get("allergies", ""))

        col1, col2 = st.columns(2)
        with col1:
            confirm = st.form_submit_button("Confirm")
        with col2:
            update = st.form_submit_button("Update & Confirm")

    if confirm:
        _set_current_employee(employee_id)
        st.success("Employee confirmed.")
        if not str(existing.get("office", "")).strip():
            st.warning("Office is empty. Orders cannot be delivered internally until an office is provided.")

    if update:
        employees[employee_key] = {
            "f_name": f_name.strip(),
            "l_name": l_name.strip(),
            "office": office.strip(),
            "extension": extension.strip(),
            "allergies": allergies.strip(),
        }
        data_store.save_employees(employees)
        _set_current_employee(employee_id)
        st.success("Employee updated and confirmed.")
        if not office.strip():
            st.warning("Office is empty. Orders cannot be delivered internally until an office is provided.")

    with st.expander("View employee list"):
        if not employees:
            st.write("No employees saved yet.")
        else:
            st.dataframe(
                [
                    {"employee_id": k, **v}
                    for k, v in sorted(employees.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else kv[0])
                ],
                hide_index=True,
            )


def _format_receipt_text(order: dict[str, Any]) -> str:
    employees = data_store.load_employees()
    employee_id = int(order.get("employee_id", 0) or 0)
    employee = employees.get(str(employee_id), {})

    delivery_office = str(order.get("delivery_office", "")).strip()
    delivery_extension = str(order.get("delivery_extension", "")).strip()
    if not delivery_office and employee:
        delivery_office = str(employee.get("office", "")).strip()
    if not delivery_extension and employee:
        delivery_extension = str(employee.get("extension", "")).strip()

    lines: list[str] = []
    lines.append("COFFEE ORDER RECEIPT")
    lines.append("=" * 40)
    lines.append(f"Order #:    {order.get('order_id', '')}")
    lines.append(f"Timestamp:  {order.get('timestamp', '')}")
    lines.append(f"Employee #: {employee_id}")
    if employee:
        name = f"{employee.get('f_name','').strip()} {employee.get('l_name','').strip()}".strip()
        if name:
            lines.append(f"Name:       {name}")
        allergies = str(employee.get("allergies", "")).strip()
        if allergies:
            lines.append(f"Allergies:  {allergies}")

    if delivery_office:
        lines.append(f"Deliver to: {delivery_office}")
        if delivery_extension:
            lines.append(f"Extension:  {delivery_extension}")

    delivery_notes = str(order.get("delivery_notes", "")).strip()
    if delivery_notes:
        lines.append(f"Notes:      {delivery_notes}")

    lines.append("-" * 40)
    lines.append("Items")
    items = order.get("items", [])
    if isinstance(items, list) and items:
        for i, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            qty = int(item.get("quantity", 1) or 1)
            drink = str(item.get("drink", "")).strip()
            size = str(item.get("size", "")).strip()
            milk = str(item.get("milk", "")).strip()
            flavor = str(item.get("flavor", "")).strip()
            pumps = int(item.get("pumps", 0) or 0)
            item_total = _as_float(item.get("total_price", 0))

            lines.append(f"{i}. {qty}x {size} {drink}")
            lines.append(f"   Milk: {milk} | Flavor: {flavor} | Pumps: {pumps}")
            lines.append(f"   Item total: ${item_total:.2f}")
    else:
        lines.append("(no items)")

    lines.append("-" * 40)
    lines.append(f"ORDER TOTAL: ${_as_float(order.get('total_price', 0)):.2f}")
    lines.append("=" * 40)
    lines.append("Thank you!")
    return "\n".join(lines) + "\n"


def order_tab() -> None:
    st.header("Order")

    if not st.session_state.employee_confirmed or st.session_state.employee_id is None:
        st.info("Go to the Employees tab and confirm an employee number first.")
        return

    employee_id = int(st.session_state.employee_id)
    employee = _employee_display(employee_id)

    menu = data_store.load_menu()
    coffees, sizes, milks, flavors, prices = _get_menu_lists(menu)

    if not coffees or not sizes or not milks or not flavors:
        st.error("Menu is missing. Update menu.json or menu.txt and refresh.")
        return

    def _records(value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, list):
            return [v for v in value if isinstance(v, dict)]
        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            try:
                return to_dict("records")
            except Exception:
                return []
        return []

    def _load_order_into_state(order: dict[str, Any]) -> None:
        items = order.get("items", [])
        cart: list[CartItem] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            cart.append(
                _cart_item_from_selection(
                    drink=str(item.get("drink", "")),
                    size=str(item.get("size", "")),
                    milk=str(item.get("milk", "")),
                    flavor=str(item.get("flavor", "")),
                    pumps=int(item.get("pumps", 0) or 0),
                    quantity=int(item.get("quantity", 1) or 1),
                    sizes=sizes,
                    prices=prices,
                )
            )

        st.session_state.cart = cart

        delivery_office = str(order.get("delivery_office", "")).strip()
        delivery_extension = str(order.get("delivery_extension", "")).strip()
        if delivery_office:
            st.session_state.delivery_mode = DELIVERY_OVERRIDE
            st.session_state.delivery_office_override = delivery_office
            st.session_state.delivery_extension_override = delivery_extension
        else:
            st.session_state.delivery_mode = DELIVERY_SAVED
            st.session_state.delivery_office_override = ""
            st.session_state.delivery_extension_override = ""

        st.session_state.delivery_notes = str(order.get("delivery_notes", "")).strip()
        st.session_state.order_confirming = False

    orders = data_store.load_orders()
    employee_orders = [o for o in orders if int(o.get("employee_id", -1) or -1) == employee_id]
    employee_orders.sort(key=lambda o: str(o.get("timestamp", "")), reverse=True)
    last_order = employee_orders[0] if employee_orders else None

    favorites = data_store.load_favorites()
    favorite = favorites.get(str(employee_id))

    if favorite or last_order:
        st.subheader("Quick reorder")
        quick_cols = st.columns(2)
        with quick_cols[0]:
            if favorite and st.button("Load favorite"):
                _load_order_into_state(favorite)
                st.success("Loaded favorite order. Review and place when ready.")
                st.rerun()
        with quick_cols[1]:
            if last_order and st.button("Load last order"):
                _load_order_into_state(last_order)
                st.success("Loaded last order. Review and place when ready.")
                st.rerun()

    def _render_bullets(items: list[str], columns: int = 2) -> None:
        if not items:
            st.write("(none)")
            return

        columns = max(1, int(columns))
        col_widgets = st.columns(columns)
        per_col = (len(items) + columns - 1) // columns
        for idx in range(columns):
            start = idx * per_col
            end = start + per_col
            chunk = items[start:end]
            if not chunk:
                continue
            with col_widgets[idx]:
                safe_items = [item.replace("\n", " ").strip() for item in chunk]
                st.markdown("\n".join([f"- {item}" for item in safe_items]))

    with st.expander("Menu (for reference)", expanded=False):
        search = st.text_input("Search menu", value="").strip().lower()
        filtered_coffees = [c for c in coffees if (search in c.lower())] if search else coffees
        filtered_milks = [m for m in milks if (search in m.lower())] if search else milks
        filtered_flavors = [f for f in flavors if (search in f.lower())] if search else flavors

        st.caption("Expand a category to view options.")

        with st.expander("Drinks", expanded=True):
            _render_bullets(filtered_coffees, columns=2)

        with st.expander("Sizes & prices"):
            rows = []
            for i, size in enumerate(sizes):
                price = prices[i] if 0 <= i < len(prices) else None
                price_text = f"${price:.2f}" if isinstance(price, float) else ""
                rows.append((size, price_text))

            table_lines = ["| Size | Base price |", "|---|---:|"]
            table_lines.extend([f"| {size} | {price_text} |" for size, price_text in rows])
            st.markdown("\n".join(table_lines))
            st.caption(f"Flavor pumps cost ${PUMP_COST:.2f} each (max {MAX_PUMPS}).")

        with st.expander("Milks"):
            _render_bullets(filtered_milks, columns=2)

        with st.expander("Flavors"):
            _render_bullets(filtered_flavors, columns=2)

    st.subheader("Delivery")
    st.radio(
        "Deliver to",
        [DELIVERY_SAVED, DELIVERY_OVERRIDE],
        key="delivery_mode",
        horizontal=True,
    )

    if st.session_state.delivery_mode == DELIVERY_OVERRIDE:
        st.info("Override active for this order.")
        st.session_state.delivery_office_override = st.text_input(
            "Office (override for this order)",
            value=st.session_state.delivery_office_override or employee.get("office", ""),
        )
        st.session_state.delivery_extension_override = st.text_input(
            "Extension (override for this order)",
            value=st.session_state.delivery_extension_override or employee.get("extension", ""),
        )
        delivery_office = str(st.session_state.delivery_office_override).strip()
        delivery_extension = str(st.session_state.delivery_extension_override).strip()
    else:
        delivery_office = str(employee.get("office", "")).strip()
        delivery_extension = str(employee.get("extension", "")).strip()

    delivery_ok, delivery_error = _validate_delivery(delivery_office, delivery_extension)

    if delivery_ok:
        destination = f"Deliver to: {delivery_office}"
        if delivery_extension:
            destination += f" (ext {delivery_extension})"
        if employee.get("name"):
            destination += f" — {employee.get('name')} (#{employee_id})"
        else:
            destination += f" — Employee #{employee_id}"
        st.success(destination)
    else:
        st.error(delivery_error)

    st.text_area(
        "Delivery notes (optional)",
        key="delivery_notes",
        placeholder="e.g., leave at front desk, call on arrival, meeting room name",
    )

    st.subheader("Add item")
    with st.form("add_item"):
        drink = st.selectbox("Drink", coffees)
        size = st.selectbox("Size", sizes)
        milk = st.selectbox("Milk", milks)
        flavor = st.selectbox("Flavor", flavors)
        pumps = st.number_input("Pumps", min_value=0, max_value=MAX_PUMPS, value=0, step=1)
        quantity = st.number_input("Quantity", min_value=1, max_value=20, value=1, step=1)
        add = st.form_submit_button("Add to order")

    if add:
        st.session_state.cart.append(
            _cart_item_from_selection(
                drink=drink,
                size=size,
                milk=milk,
                flavor=flavor,
                pumps=int(pumps),
                quantity=int(quantity),
                sizes=sizes,
                prices=prices,
            )
        )
        st.session_state.order_confirming = False
        st.success("Item added.")

    st.subheader("Current order")
    cart: list[CartItem] = st.session_state.cart
    if not cart:
        st.write("No items yet.")
        if st.session_state.last_receipt_text and st.session_state.last_receipt_filename:
            st.divider()
            st.subheader("Download receipt")
            st.download_button(
                "Download receipt",
                data=st.session_state.last_receipt_text,
                file_name=st.session_state.last_receipt_filename,
                mime="text/plain",
            )
        return

    editor_rows = []
    for item in cart:
        editor_rows.append(
            {
                "remove": False,
                "drink": item.drink,
                "size": item.size,
                "milk": item.milk,
                "flavor": item.flavor,
                "pumps": int(item.pumps),
                "qty": int(item.quantity),
                "item_total": f"${float(item.total_price):.2f}",
            }
        )

    edited = st.data_editor(
        editor_rows,
        hide_index=True,
        use_container_width=True,
        key="cart_editor",
        column_config={
            "remove": st.column_config.CheckboxColumn("Remove", help="Mark an item to remove from the order"),
            "drink": st.column_config.SelectboxColumn("Drink", options=coffees),
            "size": st.column_config.SelectboxColumn("Size", options=sizes),
            "milk": st.column_config.SelectboxColumn("Milk", options=milks),
            "flavor": st.column_config.SelectboxColumn("Flavor", options=flavors),
            "pumps": st.column_config.NumberColumn("Pumps", min_value=0, max_value=MAX_PUMPS, step=1),
            "qty": st.column_config.NumberColumn("Qty", min_value=1, max_value=20, step=1),
            "item_total": st.column_config.TextColumn("Item total", disabled=True),
        },
        disabled=["item_total"],
    )

    preview_cart: list[CartItem] = []
    for row in _records(edited):
        if bool(row.get("remove")):
            continue
        preview_cart.append(
            _cart_item_from_selection(
                drink=str(row.get("drink", "")),
                size=str(row.get("size", "")),
                milk=str(row.get("milk", "")),
                flavor=str(row.get("flavor", "")),
                pumps=int(row.get("pumps", 0) or 0),
                quantity=int(row.get("qty", 1) or 1),
                sizes=sizes,
                prices=prices,
            )
        )

    grand_total = sum(float(item.total_price) for item in preview_cart)
    st.write(f"Total: ${grand_total:.2f}")

    if st.button("Apply cart changes"):
        st.session_state.cart = preview_cart
        st.session_state.order_confirming = False
        st.rerun()

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Remove last item"):
            st.session_state.cart = cart[:-1]
            st.session_state.order_confirming = False
            st.rerun()
    with col2:
        if st.button("Clear order"):
            st.session_state.cart = []
            st.session_state.order_confirming = False
            st.rerun()
    with col3:
        review = st.button("Review & place order", type="primary", disabled=not delivery_ok)

    if review:
        st.session_state.order_confirming = True
        st.rerun()

    if st.session_state.order_confirming:
        st.divider()
        st.subheader("Confirm order")
        if employee.get("name"):
            st.write(f"Employee: #{employee_id} — {employee.get('name')}")
        else:
            st.write(f"Employee: #{employee_id}")
        st.write(f"Deliver to: {delivery_office}" + (f" (ext {delivery_extension})" if delivery_extension else ""))
        if st.session_state.delivery_notes:
            st.write(f"Notes: {st.session_state.delivery_notes}")
        if employee.get("allergies"):
            st.warning(f"Allergies on file: {employee.get('allergies')}")

        confirm_rows = [
            {
                "#": i + 1,
                "drink": item.drink,
                "size": item.size,
                "milk": item.milk,
                "flavor": item.flavor,
                "pumps": item.pumps,
                "qty": item.quantity,
                "item_total": f"${item.total_price:.2f}",
            }
            for i, item in enumerate(preview_cart)
        ]
        st.dataframe(confirm_rows, hide_index=True, use_container_width=True)
        st.write(f"Order total: ${grand_total:.2f}")

        back_col, place_col = st.columns(2)
        with back_col:
            if st.button("Back to editing"):
                st.session_state.order_confirming = False
                st.rerun()
        with place_col:
            confirm_place = st.button("Confirm & place order", type="primary")

        if confirm_place:
            orders = data_store.load_orders()
            order_id = data_store.next_order_id(orders)

            order = {
                "order_id": order_id,
                "employee_id": employee_id,
                "timestamp": data_store.now_iso(),
                "delivery_office": delivery_office,
                "delivery_extension": delivery_extension,
                "delivery_notes": str(st.session_state.delivery_notes or "").strip(),
                "items": [item.__dict__ for item in preview_cart],
                "total_price": float(grand_total),
            }

            orders.append(order)
            data_store.save_orders(orders)

            st.session_state.last_saved_order_id = order_id
            st.session_state.last_receipt_text = _format_receipt_text(order)
            st.session_state.last_receipt_filename = f"receipt_order_{order_id}.txt"
            st.session_state.cart = []
            st.session_state.order_confirming = False
            st.success(f"Order #{order_id} saved.")
            st.subheader("Download receipt")
            st.download_button(
                "Download receipt",
                data=st.session_state.last_receipt_text,
                file_name=st.session_state.last_receipt_filename,
                mime="text/plain",
            )


def history_tab() -> None:
    st.header("Order History")

    if st.session_state.employee_id is None:
        st.info("Enter an employee number in the Employees tab first.")
        return

    employee_id = int(st.session_state.employee_id)
    employee = _employee_display(employee_id)
    orders = data_store.load_orders()
    favorites = data_store.load_favorites()

    menu = data_store.load_menu()
    coffees, sizes, milks, flavors, prices = _get_menu_lists(menu)
    if not coffees or not sizes or not milks or not flavors:
        st.error("Menu is missing. Update menu.json or menu.txt and refresh.")
        return

    employee_orders = [o for o in orders if int(o.get("employee_id", -1) or -1) == employee_id]
    employee_orders.sort(key=lambda o: str(o.get("timestamp", "")), reverse=True)

    if not employee_orders:
        st.write("No orders found for this employee yet.")
        return

    st.write(f"Showing orders for employee #{employee_id}.")

    for order in employee_orders:
        order_id = order.get("order_id", "")
        timestamp = order.get("timestamp", "")
        total = _as_float(order.get("total_price", 0))

        with st.expander(f"Order #{order_id} — {timestamp} — ${total:.2f}"):
            delivery_office = str(order.get("delivery_office", "")).strip() or employee.get("office", "")
            delivery_extension = str(order.get("delivery_extension", "")).strip() or employee.get("extension", "")
            if delivery_office:
                st.write(f"Deliver to: {delivery_office}" + (f" (ext {delivery_extension})" if delivery_extension else ""))

            items = order.get("items", [])
            if isinstance(items, list):
                st.dataframe(
                    [
                        {
                            "drink": str(i.get("drink", "")),
                            "size": str(i.get("size", "")),
                            "milk": str(i.get("milk", "")),
                            "flavor": str(i.get("flavor", "")),
                            "pumps": int(i.get("pumps", 0) or 0),
                            "qty": int(i.get("quantity", 1) or 1),
                            "item_total": f"${_as_float(i.get('total_price', 0)):.2f}",
                        }
                        for i in items
                        if isinstance(i, dict)
                    ],
                    hide_index=True,
                    use_container_width=True,
                )

            if st.button(f"Re-order this order", key=f"reorder_{order_id}"):
                cart: list[CartItem] = []
                for i in items if isinstance(items, list) else []:
                    if not isinstance(i, dict):
                        continue
                    cart.append(
                        CartItem(
                            drink=str(i.get("drink", "")),
                            size=str(i.get("size", "")),
                            milk=str(i.get("milk", "")),
                            flavor=str(i.get("flavor", "")),
                            pumps=int(i.get("pumps", 0) or 0),
                            quantity=int(i.get("quantity", 1) or 1),
                            base_price=_as_float(i.get("base_price", 0)),
                            pump_price=_as_float(i.get("pump_price", 0)),
                            total_price=_as_float(i.get("total_price", 0)),
                        )
                    )
                st.session_state.cart = cart
                if delivery_office:
                    st.session_state.delivery_mode = DELIVERY_OVERRIDE
                    st.session_state.delivery_office_override = str(delivery_office).strip()
                    st.session_state.delivery_extension_override = str(delivery_extension).strip()
                else:
                    st.session_state.delivery_mode = DELIVERY_SAVED
                    st.session_state.delivery_office_override = ""
                    st.session_state.delivery_extension_override = ""
                st.session_state.order_confirming = False
                st.success("Loaded items into Current order. Go to the Order tab to confirm & save.")


def main() -> None:
    st.set_page_config(page_title="Coffee Ordering System", layout="wide")
    _ensure_state()
    data_store.ensure_json_files()

    st.title("Coffee Ordering System")

    with st.sidebar:
        st.subheader("Employee")
        if st.session_state.employee_confirmed and st.session_state.employee_id is not None:
            employee_id = int(st.session_state.employee_id)
            employee = _employee_display(employee_id)
            if employee.get("name"):
                st.write(f"#{employee_id} {employee.get('name')}")
            else:
                st.write(f"Employee #{employee_id}")
            if employee.get("office") or employee.get("extension"):
                st.write(
                    f"Office: {employee.get('office','')}".strip()
                    + (f" (ext {employee.get('extension','')})" if employee.get("extension") else "")
                )
            if st.button("Switch employee"):
                _reset_employee_state()
                st.rerun()
        else:
            st.write("No employee selected.")

    if st.session_state.employee_confirmed and st.session_state.employee_id is not None:
        employee_id = int(st.session_state.employee_id)
        employee = _employee_display(employee_id)
        caption = f"Ordering as: #{employee_id}"
        if employee.get("name"):
            caption += f" {employee.get('name')}"
        if employee.get("office"):
            caption += f" — deliver to {employee.get('office')}"
            if employee.get("extension"):
                caption += f" (ext {employee.get('extension')})"
        st.caption(caption)
    else:
        st.caption("No employee selected yet.")

    tab_employees, tab_order, tab_history = st.tabs(["Employees", "Order", "Order History"])
    with tab_employees:
        employees_tab()
    with tab_order:
        order_tab()
    with tab_history:
        history_tab()


if __name__ == "__main__":
    main()
