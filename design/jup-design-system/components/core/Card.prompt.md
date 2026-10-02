`Card` is the default container for a unit of content — a project, an asset, a news item.

```jsx
<Card
	variant="accent"
	eyebrow="Portofolio"
	title="SPBG Cililitan"
	footer={
		<Button variant="outline" size="sm">
			Detail
		</Button>
	}
>
	Stasiun pengisian bahan bakar gas dengan kapasitas layanan 240 kendaraan per hari.
</Card>
```

`accent` adds a 3px green top rule, `accent-alt` a blue one. `inverse` for dark sections.
