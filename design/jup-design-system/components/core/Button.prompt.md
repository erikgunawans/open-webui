Use `Button` for every action in a JUP interface; reach for `variant="primary"` (Pigment Green) only once per view.

```jsx
<Button variant="primary" size="lg" iconRight={<Icon name="arrow-right" />}>
	Lihat portofolio
</Button>
```

Variants: `primary` (green), `secondary` (Polynesian Blue), `outline`, `ghost`, `inverse` (white on dark sections), `danger`. Sizes `sm | md | lg`. `block` stretches full width. Pass `as="a"` with `href` for links. Hover darkens one ramp step; there is no lift or scale on press.
