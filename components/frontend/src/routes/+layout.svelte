<script>
	import '../app.css';
</script>

<nav class="sticky top-0 border-b px-5 py-3">
	<ul class="align-center flex items-center gap-2">
		<li class="mr-1 text-3xl font-extrabold">archie</li>
		<li><a href="/">home</a></li>
	</ul>
</nav>
<main class="container mx-auto pt-4">
	<slot></slot>
</main>
