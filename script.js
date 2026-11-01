// Скрипт лендинга: мобильное меню, появление блоков, проверка формы.
// Заявка уходит на POST /api/order — его принимает server.py
// и пересылает в Telegram (см. README).

(function () {
  'use strict';

  /* --- Мобильное меню --- */
  var burger = document.getElementById('burger');
  var nav = document.getElementById('nav');

  if (burger && nav) {
    burger.addEventListener('click', function () {
      var open = burger.getAttribute('aria-expanded') === 'true';
      burger.setAttribute('aria-expanded', String(!open));
      nav.classList.toggle('is-open', !open);
    });

    nav.addEventListener('click', function (event) {
      if (event.target.closest('a')) {
        burger.setAttribute('aria-expanded', 'false');
        nav.classList.remove('is-open');
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && nav.classList.contains('is-open')) {
        burger.setAttribute('aria-expanded', 'false');
        nav.classList.remove('is-open');
        burger.focus();
      }
    });
  }

  /* --- Шапка при прокрутке --- */
  var header = document.getElementById('header');
  var onScroll = function () {
    if (header) header.classList.toggle('is-scrolled', window.scrollY > 12);
  };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  /* --- Появление блоков --- */
  var blocks = document.querySelectorAll(
    '.statement__inner, .menu__head, .course, .process__text, .process__media, .review, .order__text, .order__form'
  );

  if ('IntersectionObserver' in window) {
    blocks.forEach(function (block) {
      block.classList.add('reveal');
    });

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-in');
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.08 }
    );

    blocks.forEach(function (block) {
      observer.observe(block);
    });
  }

  /* --- Заявка --- */
  var form = document.getElementById('orderForm');
  var status = document.getElementById('formStatus');

  var rules = {
    name: function (value) {
      return value.trim().length >= 2 ? '' : 'Напишите имя, чтобы знать, как к вам обращаться';
    },
    phone: function (value) {
      var digits = value.replace(/\D/g, '');
      return digits.length >= 10 ? '' : 'Нужен телефон из 10–11 цифр';
    },
    address: function (value) {
      return value.trim().length >= 5 ? '' : 'Укажите улицу, дом и квартиру';
    },
    consent: function (value, input) {
      return input.checked ? '' : 'Без согласия на обработку данных заявку принять нельзя';
    }
  };

  function checkField(input) {
    var rule = rules[input.name];
    if (!rule) return true;

    var message = rule(input.value, input);
    var field = input.closest('.field');
    var error = field.querySelector('.field__error');

    if (message) {
      field.classList.add('is-invalid');
      if (error) error.textContent = message;
      input.setAttribute('aria-invalid', 'true');
      return false;
    }

    field.classList.remove('is-invalid');
    if (error) error.textContent = '';
    input.removeAttribute('aria-invalid');
    return true;
  }

  if (form) {
    var inputs = form.querySelectorAll('input, textarea');

    inputs.forEach(function (input) {
      input.addEventListener('blur', function () {
        checkField(input);
      });
      input.addEventListener('input', function () {
        if (input.closest('.field').classList.contains('is-invalid')) {
          checkField(input);
        }
      });
    });

    // Ссылка на политику стоит внутри подписи — она не должна
    // заодно переключать галочку согласия.
    var consentLink = form.querySelector('.field--check a');
    if (consentLink) {
      consentLink.addEventListener('click', function (event) {
        event.stopPropagation();
      });
    }

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      status.textContent = '';
      status.classList.remove('is-error');

      var valid = true;
      inputs.forEach(function (input) {
        if (!checkField(input)) valid = false;
      });

      if (!valid) {
        var firstInvalid = form.querySelector('.is-invalid input, .is-invalid textarea');
        if (firstInvalid) firstInvalid.focus();
        return;
      }

      var button = form.querySelector('button[type="submit"]');
      var label = button.textContent;
      var payload = {
        name: form.elements.name.value,
        phone: form.elements.phone.value,
        pie: form.elements.pie.value,
        address: form.elements.address.value,
        note: form.elements.note.value,
        consent: form.elements.consent.checked
      };

      button.disabled = true;
      button.textContent = 'Отправляем…';

      fetch('api/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { ok: response.ok, data: data };
          });
        })
        .then(function (result) {
          if (result.ok && result.data.ok) {
            form.reset();
            status.textContent = 'Заявка принята. Перезвоним в течение 10 минут.';
            return;
          }

          if (result.data.errors) {
            showErrors(result.data.errors);
            status.textContent = 'Проверьте выделенные поля.';
            status.classList.add('is-error');
            return;
          }

          status.textContent = result.data.error || 'Не получилось отправить заявку. Позвоните нам.';
          status.classList.add('is-error');
        })
        .catch(function () {
          status.textContent = 'Сервер недоступен. Позвоните: +7 495 000-00-00.';
          status.classList.add('is-error');
        })
        .then(function () {
          button.disabled = false;
          button.textContent = label;
        });
    });
  }

  function showErrors(errors) {
    Object.keys(errors).forEach(function (name) {
      var input = form.elements[name];
      if (!input) return;
      var field = input.closest('.field');
      var error = field.querySelector('.field__error');
      if (!error) return;
      field.classList.add('is-invalid');
      error.textContent = errors[name];
      input.setAttribute('aria-invalid', 'true');
    });

    var firstInvalid = form.querySelector('.is-invalid input, .is-invalid textarea');
    if (firstInvalid) firstInvalid.focus();
  }

  /* --- Год в подвале --- */
  var year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());
})();
