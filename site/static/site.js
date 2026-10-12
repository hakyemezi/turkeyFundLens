// Draw every chart whose Vega-Lite spec the page carries inline
document.querySelectorAll(".chart > script[type='application/json']").forEach((script) => {
  const spec = JSON.parse(script.textContent);
  spec.background = null;
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  vegaEmbed(script.parentElement, spec, { actions: false, renderer: "svg", theme: dark ? "dark" : undefined });
});

// Fund search on the home page: the index is a small JSON list of code, name, universe
const input = document.getElementById("q");
if (input) {
  const results = document.getElementById("results");
  const root = input.dataset.root || "";
  let funds = null;

  const norm = (text) => text.toLocaleLowerCase("tr");

  input.addEventListener("input", async () => {
    if (!funds) {
      funds = await fetch(input.dataset.index).then((r) => r.json());
    }
    const q = norm(input.value.trim());
    results.replaceChildren();
    if (q.length < 2) return;

    const hits = funds
      .filter((f) => norm(f.c).startsWith(q) || norm(f.n).includes(q))
      .slice(0, 20);
    for (const f of hits) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `${root}fon/${f.c}.html`;
      a.textContent = `${f.c} — ${f.n}`;
      const small = document.createElement("small");
      small.textContent = ` · ${f.u}`;
      li.append(a, small);
      results.append(li);
    }
  });
}
