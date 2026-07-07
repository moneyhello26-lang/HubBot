function openTask(taskId) {
    const placeholder = document.getElementById('placeholder');
    if (placeholder) {
        placeholder.style.display = 'none';
    }
    
    const allDetails = document.querySelectorAll('.task-detail');
    allDetails.forEach(function(detail) {
        detail.style.display = 'none';
    });
    
    const selectedTask = document.getElementById('task-' + taskId);
    if (selectedTask) {
        selectedTask.style.display = 'block';
    }
}
