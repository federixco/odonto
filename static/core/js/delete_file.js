    // Delete file logic
    const deleteButtons = document.querySelectorAll('.btn-eliminar-archivo');
    deleteButtons.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const archivoId = btn.dataset.archivoId;
            const archivoNombre = btn.dataset.archivoNombre;
            if (!confirm('¿Seguro que deseas eliminar el archivo "' + archivoNombre + '"?')) {
                return;
            }
            
            try {
                const response = await fetch('/archivos/eliminar/' + archivoId + '/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken }
                });
                
                if (response.ok) {
                    window.location.reload();
                } else {
                    alert('Error al eliminar el archivo.');
                }
            } catch (err) {
                alert('Error de conexión al intentar eliminar.');
            }
        });
    });
});
