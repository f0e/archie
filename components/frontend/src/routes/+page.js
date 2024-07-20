export async function load({ params }) {
	const res = await fetch(`http://localhost:5000/account/soundcloud/78887514`);
	const item = await res.json();

	return {
		item
	};
}
