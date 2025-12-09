// Main JavaScript functionality
document.addEventListener('DOMContentLoaded', function() {

    // Add slide-in animation to option cards
    const optionCards = document.querySelectorAll('.option-card');
    optionCards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('slide-in');
    });

    // Reset card states when page loads (for back navigation)
    resetCardStates();
});

// Handle back/forward navigation
window.addEventListener('pageshow', function(event) {
    // Reset card states when returning to the page
    if (event.persisted || (window.performance && window.performance.navigation.type === 2)) {
        resetCardStates();
    }
});

// Function to reset all option cards to their original state
function resetCardStates() {
    const optionCards = document.querySelectorAll('.option-card');
    optionCards.forEach(card => {
        // Reset styles
        card.style.transform = '';
        card.style.opacity = '';
        
        // Check if card is in loading state and restore original content
        const loadingSpinner = card.querySelector('.loading-spinner');
        if (loadingSpinner) {
            // Restore original content based on card type
            const cardType = card.getAttribute('onclick');
            if (cardType && cardType.includes('feature')) {
                card.innerHTML = `
                    <div class="card-icon">
                        <i class="fas fa-lightbulb"></i>
                    </div>
                    <h3>Фича</h3>
                    <p>Исследование конкретной функциональности продукта</p>
                    <div class="card-arrow">
                        <i class="fas fa-arrow-right"></i>
                    </div>
                `;
            } else if (cardType && cardType.includes('product')) {
                card.innerHTML = `
                    <div class="card-icon">
                        <i class="fas fa-cube"></i>
                    </div>
                    <h3>Продукт</h3>
                    <p>Комплексный анализ продукта и его позиционирования</p>
                    <div class="card-arrow">
                        <i class="fas fa-arrow-right"></i>
                    </div>
                `;
            }
        }
    });
}

// Function to handle option selection
function selectOption(type) {
    // Add loading state to the selected card
    const selectedCard = event.currentTarget;
    selectedCard.style.transform = 'scale(0.95)';
    selectedCard.style.opacity = '0.8';

    // Add loading spinner
    const originalContent = selectedCard.innerHTML;
    selectedCard.innerHTML = `
        <div class="loading-spinner" style="width: 40px; height: 40px; margin: 0 auto 20px;"></div>
        <p>Загрузка...</p>
    `;

    // Navigate based on type
    setTimeout(() => {
        switch(type) {
            case 'feature':
                window.location.href = '/feature';
                break;
            case 'product':
                window.location.href = '/product';
                break;
        }
    }, 1000);
}

// Form validation and submission
function validateForm() {
    const form = document.querySelector('form');
    if (!form) return true;

    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;

    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.style.borderColor = '#ff6b6b';
            isValid = false;
        } else {
            field.style.borderColor = '#e1e5e9';
        }
    });

    return isValid;
}

// Submit form with loading state
function submitForm() {
    if (!validateForm()) {
        alert('Пожалуйста, заполните все обязательные поля');
        return;
    }

    const submitBtn = document.querySelector('.submit-btn');
    if (submitBtn) {
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';
        submitBtn.disabled = true;
    }

    // Form will be submitted normally
}

// Loading page functionality
function startReportGeneration() {
    const researchData = window.researchData;
    if (!researchData) return;

    // Show loading animation
    const loadingSpinner = document.querySelector('.loading-spinner');
    if (loadingSpinner) {
        loadingSpinner.style.display = 'block';
    }

    // Generate report
    fetch('/generate-report', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(researchData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Redirect to results page with report ID
            window.location.href = `/results?report_id=${data.report_id}`;
        } else {
            alert('Ошибка при генерации отчета: ' + (data.message || 'Неизвестная ошибка'));
            window.location.href = '/';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Произошла ошибка при генерации отчета');
        window.location.href = '/';
    });
}

// Export to PDF functionality
function exportToPDF() {
    const reportContent = document.querySelector('.report-content');
    if (!reportContent) return;

    const exportBtn = document.querySelector('.export-btn');
    if (exportBtn) {
        exportBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Экспорт...';
        exportBtn.disabled = true;
    }

    fetch('/export-pdf', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            report: reportContent.innerHTML
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Create and download PDF
            const blob = new Blob([data.content], { type: 'application/pdf' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'research-report.pdf';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } else {
            alert('Ошибка при экспорте PDF');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Произошла ошибка при экспорте');
    })
    .finally(() => {
        if (exportBtn) {
            exportBtn.innerHTML = '<i class="fas fa-download"></i> Экспорт в PDF';
            exportBtn.disabled = false;
        }
    });
}

// Copy to clipboard functionality
function copyToClipboard() {
    const reportContent = document.querySelector('.report-content');
    if (!reportContent) return;

    const text = reportContent.innerText;
    navigator.clipboard.writeText(text).then(() => {
        const copyBtn = document.querySelector('.copy-btn');
        if (copyBtn) {
            const originalText = copyBtn.innerHTML;
            copyBtn.innerHTML = '<i class="fas fa-check"></i> Скопировано!';
            setTimeout(() => {
                copyBtn.innerHTML = originalText;
            }, 2000);
        }
    }).catch(err => {
        console.error('Failed to copy: ', err);
        alert('Не удалось скопировать текст');
    });
}

// Smooth scrolling for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Add hover effects to interactive elements
document.querySelectorAll('.option-card, .action-btn, .feature-item').forEach(element => {
    element.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-2px)';
    });
    
    element.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
    });
});

// Auto-resize textareas
document.querySelectorAll('textarea').forEach(textarea => {
    textarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = this.scrollHeight + 'px';
    });
});

// Form field focus effects
document.querySelectorAll('.form-input, .form-textarea, .form-select').forEach(field => {
    field.addEventListener('focus', function() {
        this.parentElement.classList.add('focused');
    });
    
    field.addEventListener('blur', function() {
        this.parentElement.classList.remove('focused');
    });
});

// Segment selector interactions
document.querySelectorAll('.segment-option input[type="radio"]').forEach(radio => {
    radio.addEventListener('change', function() {
        // Remove active class from all options
        document.querySelectorAll('.segment-option').forEach(option => {
            option.classList.remove('active');
        });
        
        // Add active class to selected option
        if (this.checked) {
            this.closest('.segment-option').classList.add('active');
        }
    });
});

// Add visual feedback for segment selection
document.querySelectorAll('.segment-label').forEach(label => {
    label.addEventListener('click', function() {
        // Add ripple effect
        const ripple = document.createElement('div');
        ripple.className = 'ripple';
        ripple.style.position = 'absolute';
        ripple.style.borderRadius = '50%';
        ripple.style.background = 'rgba(102, 126, 234, 0.3)';
        ripple.style.transform = 'scale(0)';
        ripple.style.animation = 'ripple 0.6s linear';
        ripple.style.left = '50%';
        ripple.style.top = '50%';
        ripple.style.width = '20px';
        ripple.style.height = '20px';
        ripple.style.marginLeft = '-10px';
        ripple.style.marginTop = '-10px';
        
        this.style.position = 'relative';
        this.appendChild(ripple);
        
        setTimeout(() => {
            ripple.remove();
        }, 600);
    });
});
