// Flash message auto-hide
document.addEventListener('DOMContentLoaded', function() {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 300);
        }, 4000);
    });
});

// Update pending count
function updatePendingCount() {
    if (window.location.pathname.includes('/admin/')) {
        fetch('/api/leave/count')
            .then(response => response.json())
            .then(data => {
                const badge = document.getElementById('pending-count');
                if (badge) {
                    badge.textContent = data.count;
                }
            })
            .catch(error => console.error('Error fetching pending count:', error));
    }
}

// Call updatePendingCount on page load and periodically
document.addEventListener('DOMContentLoaded', function() {
    updatePendingCount();
    setInterval(updatePendingCount, 30000); // Update every 30 seconds
});

// Apply Leave Form Functionality
if (document.getElementById('leave-form')) {
    const reasonTextarea = document.getElementById('reason');
    const wordCount = document.getElementById('word-count');
    const sessionBtns = document.querySelectorAll('.session-btn');
    const fromDate = document.getElementById('from_date');
    const toDate = document.getElementById('to_date');
    const numDays = document.getElementById('num_days');
    const sessionType = document.getElementById('session_type');

    // Word counter
    reasonTextarea.addEventListener('input', function() {
        const words = this.value.trim().split(/\s+/).filter(word => word.length > 0).length;
        wordCount.textContent = words;
        if (words > 500) {
            this.value = this.value.trim().split(/\s+/).slice(0, 500).join(' ');
            wordCount.textContent = 500;
        }
    });

    // Session selection
    sessionBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            sessionBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            sessionType.value = this.dataset.value;
        });
    });

    // Date calculation
    function calculateDays() {
        const from = new Date(fromDate.value);
        const to = new Date(toDate.value);
        if (from && to && from <= to) {
            const diffTime = Math.abs(to - from);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
            const session = sessionType.value;
            if (session === 'AN' || session === 'FN') {
                numDays.value = 0.5;
            } else {
                numDays.value = diffDays;
            }
        } else {
            numDays.value = '';
        }
    }

    fromDate.addEventListener('change', calculateDays);
    toDate.addEventListener('change', calculateDays);
    sessionType.addEventListener('change', calculateDays);

    // Signature canvases
    const studentCanvas = document.getElementById('student-canvas');
    const parentCanvas = document.getElementById('parent-canvas');
    const studentSignature = document.getElementById('student_signature');
    const parentSignature = document.getElementById('parent_signature');
    const clearStudent = document.getElementById('clear-student');
    const clearParent = document.getElementById('clear-parent');

    let studentCtx = studentCanvas.getContext('2d');
    let parentCtx = parentCanvas.getContext('2d');
    let isDrawing = false;

    function initCanvas(canvas, ctx) {
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = '#111111';
        ctx.lineWidth = 2.5;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
    }

    initCanvas(studentCanvas, studentCtx);
    initCanvas(parentCanvas, parentCtx);

    function startDrawing(e, ctx) {
        isDrawing = true;
        ctx.beginPath();
        ctx.moveTo(e.offsetX, e.offsetY);
    }

    function draw(e, ctx) {
        if (!isDrawing) return;
        ctx.lineTo(e.offsetX, e.offsetY);
        ctx.stroke();
    }

    function stopDrawing() {
        isDrawing = false;
    }

    studentCanvas.addEventListener('mousedown', (e) => startDrawing(e, studentCtx));
    studentCanvas.addEventListener('mousemove', (e) => draw(e, studentCtx));
    studentCanvas.addEventListener('mouseup', stopDrawing);
    studentCanvas.addEventListener('mouseout', stopDrawing);

    parentCanvas.addEventListener('mousedown', (e) => startDrawing(e, parentCtx));
    parentCanvas.addEventListener('mousemove', (e) => draw(e, parentCtx));
    parentCanvas.addEventListener('mouseup', stopDrawing);
    parentCanvas.addEventListener('mouseout', stopDrawing);

    function clearCanvas(canvas, ctx, signatureInput) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        initCanvas(canvas, ctx);
        signatureInput.value = '';
    }

    clearStudent.addEventListener('click', () => clearCanvas(studentCanvas, studentCtx, studentSignature));
    clearParent.addEventListener('click', () => clearCanvas(parentCanvas, parentCtx, parentSignature));

    // Convert canvas to base64 on form submit
    document.getElementById('leave-form').addEventListener('submit', function(e) {
        studentSignature.value = studentCanvas.toDataURL('image/png').split(',')[1];
        parentSignature.value = parentCanvas.toDataURL('image/png').split(',')[1];
    });
}