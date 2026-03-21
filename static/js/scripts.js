document.addEventListener('DOMContentLoaded', () => {
    const btnGerar = document.querySelector('.btn-gerar');
    if (btnGerar) {
        btnGerar.addEventListener('click', (e) => {
            btnGerar.style.opacity = '0.7';
            btnGerar.innerText = 'Processando com Llama 3...';
            // Criamos um efeito simples de "pulsar" via JS
            btnGerar.style.cursor = 'not-allowed';
        });
    }
    
    // Feedback Range
    const range = document.getElementById('scoreRange');
    const out = document.getElementById('scoreOutput');
    if(range && out) {
        range.addEventListener('input', () => {
            out.innerText = range.value;
        });
    }
});