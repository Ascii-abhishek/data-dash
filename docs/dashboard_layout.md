# Dashboard Layout

Dashboards render as a responsive card grid. The implementation follows two stable patterns:

- Dashboard pages are made of cards arranged on a grid, matching the model used by tools like Metabase.
- Streamlit layout primitives (`st.columns` and `st.container`) own the structure, while CSS only polishes spacing, borders, and the narrow-screen single-column fallback.

## Implementation

- `app/dashboard_grid.py` owns the reusable grid renderer.
- `app/dashboard.py` owns dashboard controls, card headers, and card actions.
- `app/graphs.py` owns chart sizing through a `context="dashboard"` option.

Dashboard cards default to two columns. When the viewport is narrow, CSS stacks each row into one column. All chart types stay inside the same bordered card shell. Candlestick charts use compact dashboard heights for the price and volume panels so they fit half-width cards.

## References

- Metabase dashboard cards/grid model: https://www.metabase.com/docs/latest/dashboards/introduction
- Streamlit layout primitives: https://docs.streamlit.io/develop/api-reference/layout
- Streamlit Altair chart sizing: https://docs.streamlit.io/develop/api-reference/charts/st.altair_chart
