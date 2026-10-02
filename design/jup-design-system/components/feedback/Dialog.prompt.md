`Dialog` interrupts to confirm or collect something short.

```jsx
<Dialog
	title="Ajukan permintaan sambungan"
	footer={
		<>
			<Button variant="ghost" onClick={close}>
				Batal
			</Button>
			<Button>Kirim</Button>
		</>
	}
	onClose={close}
>
	<Field label="Nama pemohon">
		<Input />
	</Field>
</Dialog>
```
