<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password') displayInfo=(realm.password && realm.registrationAllowed && !registrationDisabled??); section>

  <#if section="header">
    <p class="aminra-subtitle">${msg("loginAccountTitle")}</p>

  <#elseif section="form">
    <#if realm.password>
      <form id="kc-form-login" class="aminra-form" onsubmit="login.disabled = true; return true;" action="${url.loginAction}" method="post">
        <div class="aminra-field">
          <label for="username" class="aminra-label">
            <#if !realm.loginWithEmailAllowed>${msg("username")}<#elseif !realm.registrationEmailAsUsername>${msg("usernameOrEmail")}<#else>${msg("email")}</#if>
          </label>
          <input tabindex="1" id="username" name="username" value="${(login.username!'')}" type="text"
                 autofocus autocomplete="off" class="aminra-input"
                 aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>"/>
          <#if messagesPerField.existsError('username','password')>
            <span id="input-error" class="aminra-error" aria-live="polite">
              ${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}
            </span>
          </#if>
        </div>

        <div class="aminra-field">
          <label for="password" class="aminra-label">${msg("password")}</label>
          <input tabindex="2" id="password" name="password" type="password" autocomplete="off" class="aminra-input"
                 aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>"/>
        </div>

        <div class="aminra-row">
          <#if realm.rememberMe && !usernameHidden??>
            <label class="aminra-checkbox-label">
              <#if login.rememberMe??>
                <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox" class="aminra-checkbox" checked>
              <#else>
                <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox" class="aminra-checkbox">
              </#if>
              <span>${msg("rememberMe")}</span>
            </label>
          <#else>
            <span></span>
          </#if>

          <#if realm.resetPasswordAllowed>
            <a tabindex="5" href="${url.loginResetCredentialsUrl}" class="aminra-link">${msg("doForgotPassword")}</a>
          </#if>
        </div>

        <input type="hidden" id="id-hidden-input" name="credentialId"
               <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>

        <button tabindex="4" class="aminra-submit" name="login" id="kc-login" type="submit">
          ${msg("doLogIn")}
        </button>
      </form>
    </#if>

  <#elseif section="info">
    <#if realm.password && realm.registrationAllowed && !registrationDisabled??>
      <p>${msg("noAccount")} <a tabindex="6" href="${url.registrationUrl}">${msg("doRegister")}</a></p>
    </#if>

  </#if>

</@layout.registrationLayout>
