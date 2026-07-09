function openTask(taskId) {
    const dashboard = document.getElementById('dashboard');
    const placeholder = document.getElementById('placeholder');
    
    if (placeholder) {
        placeholder.style.display = 'none';
    }
    
    const allDetails = document.querySelectorAll('.task-detail');
    allDetails.forEach(function(detail) {
        detail.style.display = 'none';
    });
    
    const allItems = document.querySelectorAll('.task-item');
    allItems.forEach(function(item) {
        item.classList.remove('active');
    });
    
    const selectedTask = document.getElementById('task-' + taskId);
    if (selectedTask) {
        selectedTask.style.display = 'block';
    }
    
    const selectedItem = document.getElementById('item-' + taskId);
    if (selectedItem) {
        selectedItem.classList.add('active');
    }
    
    if (window.innerWidth <= 860) {
        dashboard.classList.remove('mobile-hidden');
        dashboard.classList.add('mobile-open');
    }
}

function closeTask() {
    const dashboard = document.getElementById('dashboard');
    if (window.innerWidth <= 860) {
        dashboard.classList.remove('mobile-open');
        dashboard.classList.add('mobile-hidden');
    }
}

function updateFileName(taskId) {
    const input = document.getElementById('file-' + taskId);
    const label = document.getElementById('label-' + taskId);
    const labelText = document.getElementById('label-text-' + taskId);
    if (input.files && input.files.length > 0) {
        if (labelText) {
            labelText.textContent = '📎 ' + input.files[0].name;
        }
        label.classList.remove('btn-file');
        label.classList.add('file-chip');
    }
}
