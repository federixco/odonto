document.addEventListener('DOMContentLoaded', () => {
    const viewBtn = document.getElementById('view-mode-btn');
    const viewMenu = document.getElementById('view-mode-menu');
    const explorerContainer = document.getElementById('explorer-container');
    const viewOptions = document.querySelectorAll('.view-option');
    
    if (!viewBtn || !viewMenu || !explorerContainer) return;

    // Load saved preference
    const allowedModes = ['view-list', 'view-details', 'view-tiles', 'view-icons'];
    let savedView = 'view-tiles';
    try {
        savedView = localStorage.getItem('doc_file_view_mode') || savedView;
    } catch (_) {
        // La preferencia es opcional si el navegador bloquea el almacenamiento.
    }
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
            const mode = validMode(btn.getAttribute('data-view'));
            applyViewMode(mode);
            try {
                localStorage.setItem('doc_file_view_mode', mode);
            } catch (_) {
                // Cambiar la vista sigue funcionando sin persistir la elección.
            }
            viewMenu.setAttribute('hidden', '');
            viewBtn.setAttribute('aria-expanded', 'false');
        });
    });

    function applyViewMode(mode) {
        mode = validMode(mode);
        // No borrar folder-root ni las demás clases de estructura del panel.
        explorerContainer.classList.remove(...allowedModes);
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

    function validMode(mode) {
        return allowedModes.includes(mode) ? mode : 'view-tiles';
    }
});
