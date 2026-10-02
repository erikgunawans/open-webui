`Toast` confirms that something happened. It never carries an action the user must take — that is `Alert` or `Dialog`.

```jsx
<Toast
	tone="success"
	title="Tersimpan"
	message="Perubahan profil aset telah disimpan."
	onClose={close}
/>
```
