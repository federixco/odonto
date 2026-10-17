/* Aviso informativo: no acepta/rechaza ni modifica cookies de Django. */
(() => {
    "use strict";
    const notice = document.getElementById("doc-cookie-notice");
    if (!notice) return;
    const key = "doc_cookie_notice_v1";
    const root = document.documentElement;
    let observer;
    const hide = () => {
        const restoreFocus = notice.contains(document.activeElement);
        notice.hidden = true;
        root.classList.remove("doc-cookie-notice-open");
        root.style.removeProperty("--doc-cookie-notice-height");
        observer?.disconnect();
        if (restoreFocus) document.getElementById("contenido")?.focus({ preventScroll: true });
    };
    try { if (localStorage.getItem(key) === "seen") return; }
    catch (_) { /* El aviso sigue funcionando si el navegador bloquea almacenamiento. */ }
    notice.hidden = false;
    const reserveSpace = () => root.style.setProperty("--doc-cookie-notice-height", `${notice.getBoundingClientRect().height}px`);
    root.classList.add("doc-cookie-notice-open");
    reserveSpace();
    if (typeof ResizeObserver !== "undefined") {
        observer = new ResizeObserver(reserveSpace);
        observer.observe(notice);
    }
    notice.querySelector("[data-cookie-dismiss]").addEventListener("click", () => {
        try { localStorage.setItem(key, "seen"); }
        catch (_) { /* Cierra esta vista aunque no pueda recordar otras visitas. */ }
        hide();
    });
    window.addEventListener("storage", event => {
        if (event.key === key && event.newValue === "seen") hide();
    });
})();
