document.addEventListener('DOMContentLoaded', () => {
    const viewBtn = document.getElementById('view-mode-btn');
    const viewMenu = document.getElementById('view-mode-menu');
    const explorerContainer = document.getElementById('explorer-container');
    const viewOptions = document.querySelectorAll('.view-option');
    
    if (!viewBtn || !viewMenu || !explorerContainer) return;

    // Load saved preference
    const savedView = localStorage.getItem('doc_file_view_mode') || 'view-tiles';
    applyViewMode(savedView);

    // Toggle menu
    viewBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = viewMenu.hasAttribute('hidden');
        if (isHidden) {
            viewMenu.removeAttribute('hidden');
            viewBtn.setAttribute('aria-expanded', 'true');
        } else {
            viewMenu.setAttribute('hidden', '');
            viewBtn.setAttribute('aria-expanded', 'false');
        }
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!viewBtn.contains(e.target) && !viewMenu.contains(e.target)) {
            viewMenu.setAttribute('hidden', '');
            viewBtn.setAttribute('aria-expanded', 'false');
        }
    });

    // Handle option click
    viewOptions.forEach(btn => {
        btn.addEventListener('click', () => {
            const mode = btn.getAttribute('data-view');
            applyViewMode(mode);
            localStorage.setItem('doc_file_view_mode', mode);
            viewMenu.setAttribute('hidden', '');
            viewBtn.setAttribute('aria-expanded', 'false');
        });
    });

    function applyViewMode(mode) {
        // Remove all view-* classes
        explorerContainer.className = 'explorer-container';
        // Add selected mode
        explorerContainer.classList.add(mode);
        
        // Update active state in menu
        viewOptions.forEach(btn => {
            if (btn.getAttribute('data-view') === mode) {
                btn.classList.add('is-active');
            } else {
                btn.classList.remove('is-active');
            }
        });
    }
});
