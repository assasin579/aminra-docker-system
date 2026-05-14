<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=messagesPerField.exists('global') displayRequiredFields=false; section>

  <#if section="header">
    <p class="aminra-subtitle">${msg("registerTitle")}</p>

  <#elseif section="form">
    <form id="kc-register-form" class="aminra-form" action="${url.registrationAction}" method="post">

      <div class="aminra-field">
        <label for="firstName" class="aminra-label">${msg("firstName")}</label>
        <input type="text" id="firstName" class="aminra-input" name="firstName"
               value="${(register.formData.firstName!'')}"
               aria-invalid="<#if messagesPerField.existsError('firstName')>true</#if>"/>
        <#if messagesPerField.existsError('firstName')>
          <span class="aminra-error">${kcSanitize(messagesPerField.get('firstName'))?no_esc}</span>
        </#if>
      </div>

      <div class="aminra-field">
        <label for="lastName" class="aminra-label">${msg("lastName")}</label>
        <input type="text" id="lastName" class="aminra-input" name="lastName"
               value="${(register.formData.lastName!'')}"
               aria-invalid="<#if messagesPerField.existsError('lastName')>true</#if>"/>
        <#if messagesPerField.existsError('lastName')>
          <span class="aminra-error">${kcSanitize(messagesPerField.get('lastName'))?no_esc}</span>
        </#if>
      </div>

      <div class="aminra-field">
        <label for="email" class="aminra-label">${msg("email")}</label>
        <input type="text" id="email" class="aminra-input" name="email"
               value="${(register.formData.email!'')}" autocomplete="email"
               aria-invalid="<#if messagesPerField.existsError('email')>true</#if>"/>
        <#if messagesPerField.existsError('email')>
          <span class="aminra-error">${kcSanitize(messagesPerField.get('email'))?no_esc}</span>
        </#if>
      </div>

      <#if !realm.registrationEmailAsUsername>
        <div class="aminra-field">
          <label for="username" class="aminra-label">${msg("username")}</label>
          <input type="text" id="username" class="aminra-input" name="username"
                 value="${(register.formData.username!'')}" autocomplete="username"
                 aria-invalid="<#if messagesPerField.existsError('username')>true</#if>"/>
          <#if messagesPerField.existsError('username')>
            <span class="aminra-error">${kcSanitize(messagesPerField.get('username'))?no_esc}</span>
          </#if>
        </div>
      </#if>

      <#if passwordRequired??>
        <div class="aminra-field">
          <label for="password" class="aminra-label">${msg("password")}</label>
          <input type="password" id="password" class="aminra-input" name="password"
                 autocomplete="new-password"
                 aria-invalid="<#if messagesPerField.existsError('password','password-confirm')>true</#if>"/>
          <#if messagesPerField.existsError('password')>
            <span class="aminra-error">${kcSanitize(messagesPerField.get('password'))?no_esc}</span>
          </#if>
        </div>

        <div class="aminra-field">
          <label for="password-confirm" class="aminra-label">${msg("passwordConfirm")}</label>
          <input type="password" id="password-confirm" class="aminra-input" name="password-confirm"
                 aria-invalid="<#if messagesPerField.existsError('password-confirm')>true</#if>"/>
          <#if messagesPerField.existsError('password-confirm')>
            <span class="aminra-error">${kcSanitize(messagesPerField.get('password-confirm'))?no_esc}</span>
          </#if>
        </div>
      </#if>

      <#if recaptchaRequired??>
        <div class="aminra-field">
          <div class="g-recaptcha" data-size="compact" data-sitekey="${recaptchaSiteKey}"></div>
        </div>
      </#if>

      <button class="aminra-submit" type="submit">${msg("doRegister")}</button>
    </form>

    <div class="aminra-card-footer">
      <p>${msg("backToLogin")?no_esc} <a href="${url.loginUrl}">${msg("doLogIn")}</a></p>
    </div>

  </#if>

</@layout.registrationLayout>
