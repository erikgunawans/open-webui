`Tag` is a filter chip or a removable keyword. Unlike `Badge` it is interactive and sentence-case.

```jsx
<Tag selected onClick={() => setFilter("gas")}>Gas</Tag>
<Tag onRemove={() => drop("SPBG")}>SPBG</Tag>
```
