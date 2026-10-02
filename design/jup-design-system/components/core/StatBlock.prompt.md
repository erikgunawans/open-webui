`StatBlock` sets a number the way JUP sets numbers: tabular figures, tight tracking, a wide-tracked label above and the period underneath.

```jsx
<StatBlock
	label="Kapasitas terpasang"
	value="12,4"
	unit="MWp"
	note="Per Desember 2024"
	tone="brand"
/>
```

Always attach a period or source to `note` — a figure without one is not publishable.
