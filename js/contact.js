function validateEmail(email) {
  const re = /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i;
  return re.test(email);
}

function showError(fieldId, show) {
  const field = document.getElementById(fieldId);
  const error = document.getElementById(fieldId + '-error');

  if (show) {
    field.classList.add('error');
    error.classList.remove('hidden');
  } else {
    field.classList.remove('error');
    error.classList.add('hidden');
  }
}

function handleSubmit(event) {
  event.preventDefault();

  const name = document.getElementById('name').value.trim();
  const email = document.getElementById('email').value.trim();
  const subject = document.getElementById('subject').value.trim();
  const message = document.getElementById('message').value.trim();

  let isValid = true;

  if (!name) {
    showError('name', true);
    isValid = false;
  } else {
    showError('name', false);
  }

  if (!email || !validateEmail(email)) {
    showError('email', true);
    isValid = false;
  } else {
    showError('email', false);
  }

  if (!subject) {
    showError('subject', true);
    isValid = false;
  } else {
    showError('subject', false);
  }

  if (!message || message.length < 10) {
    showError('message', true);
    isValid = false;
  } else {
    showError('message', false);
  }

  if (isValid) {
    document.getElementById('form-container').classList.add('hidden');
    document.getElementById('success-container').classList.remove('hidden');
  }

  return false;
}

function resetForm() {
  document.getElementById('contact-form').reset();
  document.getElementById('form-container').classList.remove('hidden');
  document.getElementById('success-container').classList.add('hidden');

  ['name', 'email', 'subject', 'message'].forEach(field => {
    showError(field, false);
  });
}
