/*
 * CBT quiz-taking script.
 *
 * Matches the JSON shape returned by quiz_data_view / save_quiz_view:
 *   { data: [ { id, text, type: 'MCQ'|'SHORT', image, options: {A,B,C,D}|null } ],
 *     time_left: <seconds> }
 *
 * Supports both MCQ (radio buttons over A-D) and SHORT (free-text input)
 * question types, and resumes an in-progress attempt's real time-left on
 * reload instead of restarting the timer.
 */

(function () {
    const dataUrl = window.location.pathname.endsWith('/')
        ? `${window.location.pathname}data/`
        : `${window.location.pathname}/data/`;
    const saveUrl = window.location.pathname.endsWith('/')
        ? `${window.location.pathname}save/`
        : `${window.location.pathname}/save/`;

    const quizBox = document.getElementById('quiz-box');
    const timerBox = document.getElementById('timer-box');
    const quizForm = document.getElementById('quiz-form');
    const resultBox = document.getElementById('result-box');
    const scoreText = document.getElementById('score-text');
    const detailsBox = document.getElementById('details-box');
    const submitBtn = document.getElementById('submit-btn');

    let timer;
    let submitting = false;

    function getCookie(name) {
        const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return match ? decodeURIComponent(match[2]) : null;
    }

    function startTimer(seconds) {
        let time = seconds;
        updateTimerDisplay(time);

        timer = setInterval(() => {
            time--;
            if (time <= 0) {
                clearInterval(timer);
                updateTimerDisplay(0);
                sendData(); // Auto-submit when time runs out
                return;
            }
            updateTimerDisplay(time);
        }, 1000);
    }

    function updateTimerDisplay(time) {
        const mins = Math.floor(time / 60);
        const secs = time % 60;
        const label = `${mins}:${secs < 10 ? '0' : ''}${secs}`;
        timerBox.innerHTML = time <= 60
            ? `<b class="text-danger">Time Left: ${label}</b>`
            : `<b>Time Left: ${label}</b>`;
    }

    function renderQuestion(q, index) {
        const wrapper = document.createElement('div');
        wrapper.className = 'mb-4 pb-3 border-bottom';

        const heading = document.createElement('p');
        heading.className = 'h6 fw-bold';
        heading.innerHTML = `${index + 1}. ${q.text}`;
        wrapper.appendChild(heading);

        if (q.image) {
            const img = document.createElement('img');
            img.src = q.image;
            img.alt = 'Question image';
            img.className = 'img-fluid rounded mb-2';
            img.style.maxHeight = '260px';
            wrapper.appendChild(img);
        }

        if (q.type === 'MCQ' && q.options) {
            Object.keys(q.options).forEach((letter) => {
                const optionText = q.options[letter];
                if (!optionText) return;

                const optionWrap = document.createElement('div');
                optionWrap.className = 'form-check mb-1';

                const input = document.createElement('input');
                input.className = 'form-check-input';
                input.type = 'radio';
                input.name = String(q.id);
                input.id = `q${q.id}_${letter}`;
                input.value = letter;

                const label = document.createElement('label');
                label.className = 'form-check-label';
                label.setAttribute('for', `q${q.id}_${letter}`);
                label.textContent = `${letter}. ${optionText}`;

                optionWrap.appendChild(input);
                optionWrap.appendChild(label);
                wrapper.appendChild(optionWrap);
            });
        } else {
            // SHORT answer
            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'form-control';
            input.name = String(q.id);
            input.placeholder = 'Type your answer';
            input.autocomplete = 'off';
            wrapper.appendChild(input);
        }

        return wrapper;
    }

    function loadQuiz() {
        quizBox.innerHTML = '<div class="text-muted">Loading questions&hellip;</div>';

        fetch(dataUrl, { credentials: 'same-origin' })
            .then((res) => {
                if (!res.ok) {
                    return res.json().then((err) => { throw new Error(err.error || 'Unable to load exam.'); });
                }
                return res.json();
            })
            .then((response) => {
                quizBox.innerHTML = '';
                response.data.forEach((q, index) => {
                    quizBox.appendChild(renderQuestion(q, index));
                });
                startTimer(response.time_left);
            })
            .catch((err) => {
                quizBox.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
                if (submitBtn) submitBtn.disabled = true;
            });
    }

    function sendData() {
        if (submitting) return;
        submitting = true;
        clearInterval(timer);

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = 'Submitting&hellip;';
        }

        const formData = new FormData(quizForm);

        fetch(saveUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: formData,
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.error) {
                    alert(data.error);
                    submitting = false;
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = 'Finish Exam';
                    }
                    return;
                }

                quizForm.classList.add('d-none');
                resultBox.classList.remove('d-none');

                scoreText.innerHTML = data.passed
                    ? `<span class="text-success">Passed! Score: ${data.score}%</span>`
                    : `<span class="text-danger">Not Passed. Score: ${data.score}%</span>`;

                if (detailsBox && Array.isArray(data.results)) {
                    detailsBox.innerHTML = data.results.map((r, i) => `
                        <div class="border-bottom py-2">
                            <div class="fw-bold">${i + 1}. ${r.question}</div>
                            <div class="small ${r.is_correct ? 'text-success' : 'text-danger'}">
                                Your answer: ${r.answered}
                                ${r.is_correct ? '' : ` &mdash; Correct answer: ${r.correct}`}
                            </div>
                        </div>
                    `).join('');
                }
            })
            .catch(() => {
                alert('Something went wrong while submitting. Please check your connection and try again.');
                submitting = false;
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'Finish Exam';
                }
            });
    }

    quizForm.addEventListener('submit', (e) => {
        e.preventDefault();
        if (confirm('Are you sure you want to end the exam?')) {
            sendData();
        }
    });

    loadQuiz();
})();
