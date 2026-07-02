/* ============================================================
   FixGo – Login Page JavaScript
   Handles: client-side validation, API login
   ============================================================ */

(function () {
  "use strict";

  // ── DOM refs ──
  const form        = document.getElementById("loginForm");
  const emailInput  = document.getElementById("email");
  const pwInput     = document.getElementById("password");
  const emailError  = document.getElementById("emailError");
  const pwError     = document.getElementById("passwordError");
  const remember    = document.getElementById("remember");
  const signinBtn   = document.getElementById("signinBtn");
  const notification = document.getElementById("notification");

  // Cache the button's original label so we can restore it after loading
  const signinDefaultHTML = signinBtn.innerHTML;
  const spinnerHTML = '<span class="spinner"></span> Signing in…';

  // ── Helpers ──
  function showNotification(message, type) {
    notification.textContent = message;
    notification.className   = `notification ${type}`;
  }

  function hideNotification() {
    notification.className = "notification hidden";
  }

  function setFieldError(input, errorEl, message) {
    input.classList.add("input-error");
    errorEl.textContent = message;
  }

  function clearFieldError(input, errorEl) {
    input.classList.remove("input-error");
    errorEl.textContent = "";
  }

  function setLoading(loading) {
    signinBtn.disabled = loading;
    signinBtn.innerHTML = loading ? spinnerHTML : signinDefaultHTML;
  }

  // ── Validate email format ──
  function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  // ── Real-time field validation ──
  emailInput.addEventListener("blur", function () {
    const v = emailInput.value.trim();
    if (!v) {
      setFieldError(emailInput, emailError, "Email is required.");
    } else if (!isValidEmail(v)) {
      setFieldError(emailInput, emailError, "Enter a valid email address.");
    } else {
      clearFieldError(emailInput, emailError);
    }
  });

  emailInput.addEventListener("input", function () {
    if (emailInput.value.trim()) clearFieldError(emailInput, emailError);
  });

  pwInput.addEventListener("blur", function () {
    if (!pwInput.value) {
      setFieldError(pwInput, pwError, "Password is required.");
    } else {
      clearFieldError(pwInput, pwError);
    }
  });

  pwInput.addEventListener("input", function () {
    if (pwInput.value) clearFieldError(pwInput, pwError);
  });

  // ── Form submit ──
  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    hideNotification();

    const email    = emailInput.value.trim();
    const password = pwInput.value;
    let   valid    = true;

    // Validate
    if (!email) {
      setFieldError(emailInput, emailError, "Email is required.");
      valid = false;
    } else if (!isValidEmail(email)) {
      setFieldError(emailInput, emailError, "Enter a valid email address.");
      valid = false;
    } else {
      clearFieldError(emailInput, emailError);
    }

    if (!password) {
      setFieldError(pwInput, pwError, "Password is required.");
      valid = false;
    } else {
      clearFieldError(pwInput, pwError);
    }

    if (!valid) return;

    // Submit
    setLoading(true);

    try {
      const response = await fetch("/login", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          email,
          password,
          remember: remember.checked
        }),
        credentials: "include"
      });

      const data = await response.json();

      if (response.ok && data.success) {
        showNotification("Login successful! Redirecting…", "success");
        // Server tells us where to go: customers -> /dashboard,
        // workers -> /worker/dashboard. Fall back to /dashboard
        // if it's ever missing.
        const target = data.redirect || "/dashboard";
        setTimeout(function () {
          window.location.href = target;
        }, 800);
      } else {
        const msg = data.message || "Login failed. Please try again.";
        showNotification(msg, "error");

        // Highlight relevant field
        if (response.status === 404) {
          setFieldError(emailInput, emailError, "No account found with this email.");
        } else if (response.status === 401) {
          setFieldError(pwInput, pwError, "Incorrect password.");
        }
      }
    } catch (err) {
      showNotification("Network error. Please check your connection and try again.", "error");
    } finally {
      setLoading(false);
    }
  });

})();