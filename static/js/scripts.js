function applyFontScale(size) {
    document.documentElement.style.fontSize = size + 'px';
    localStorage.setItem('font_scale', String(size));
}

window.toggleContrast = function toggleContrast() {
    document.body.classList.toggle('high-contrast');
    localStorage.setItem('contrast', document.body.classList.contains('high-contrast'));
};

window.increaseFont = function increaseFont() {
    applyFontScale(18);
};

window.decreaseFont = function decreaseFont() {
    applyFontScale(15);
};

document.addEventListener('DOMContentLoaded', function() {
    if (localStorage.getItem('contrast') === 'true') {
        document.body.classList.add('high-contrast');
    }

    const fontScale = parseInt(localStorage.getItem('font_scale') || '', 10);
    if (!Number.isNaN(fontScale)) {
        document.documentElement.style.fontSize = fontScale + 'px';
    }

    document.querySelectorAll('[data-loading-form]').forEach(function(form) {
        form.addEventListener('submit', function() {
            const buttonId = form.getAttribute('data-loading-button-id');
            const button = buttonId
                ? document.getElementById(buttonId)
                : form.querySelector('[data-loading-button]');
            const loadingText = form.getAttribute('data-loading-text') || 'Aguarde...';

            if (button) {
                button.disabled = true;
                button.style.opacity = '0.72';
                button.textContent = loadingText;
            }
        });
    });

    const range = document.getElementById('scoreRange');
    const out = document.getElementById('scoreOutput');
    if (range && out) {
        const syncScore = function() {
            out.textContent = range.value;
        };
        syncScore();
        range.addEventListener('input', syncScore);
    }

    document.querySelectorAll('[data-toggle-target]').forEach(function(button) {
        const target = document.getElementById(button.getAttribute('data-toggle-target'));
        if (!target) {
            return;
        }

        button.addEventListener('click', function() {
            target.classList.toggle('is-hidden');
            button.setAttribute('aria-expanded', String(!target.classList.contains('is-hidden')));
        });
    });
});
