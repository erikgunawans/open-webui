`Icon` inlines a glyph file so it takes `currentColor` — never inline a hand-drawn path in JUP work.

```jsx
<Icon name="arrow-right" size={18} />
<Icon name="map-pin" base="../assets/icons/ui" />
```

Set `base` to wherever you copied `assets/icons/ui` relative to the page. For the five JUP sector marks use `SectorIcon` instead.
