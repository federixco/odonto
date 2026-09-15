(() => {
    const root = document.querySelector("[data-study-access]");
    if (!root) return;

    const search = root.querySelector("[data-access-search]");
    const status = root.querySelector("[data-access-status]");
    const cards = [...root.querySelectorAll("[data-access-card]")];
    const empty = root.querySelector("[data-access-empty]");
    if (!search || !status || !cards.length) return;

    const normalize = (value) => value
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();

    const filter = () => {
        const query = normalize(search.value);
        const selectedStatus = status.value;
        let visible = 0;

        cards.forEach((card) => {
            const matchesText = normalize(card.dataset.search || "").includes(query);
            const matchesStatus = !selectedStatus || card.dataset.status === selectedStatus;
            const show = matchesText && matchesStatus;
            card.hidden = !show;
            if (show) visible += 1;
        });

        if (empty) empty.hidden = visible !== 0;
    };

    search.addEventListener("input", filter);
    status.addEventListener("change", filter);
})();
