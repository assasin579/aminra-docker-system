<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username') displayInfo=true; section>

  <#if section="header">
    <p class="aminra-subtitle">${msg("emailForgotTitle")}</p>

  <#elseif section="form">
    <form id="kc-reset-password-form" class="aminra-form" action="${url.loginAction}" method="post">
      <div class="aminra-field">
        <label for="username" class="aminra-label">
          <#if !realm.loginWithEmailAllowed>${msg("username")}<#elseif !realm.registrationEmailAsUsername>${msg("usernameOrEmail")}<#else>${msg("email")}</#if>
        </label>
        <input type="text" id="username" name="username" class="aminra-input" autofocus
               value="${(auth.attemptedUsername!'')}"
               aria-invalid="<#if messagesPerField.existsError('username')>true</#if>"/>
        <#if messagesPerField.existsError('username')>
          <span class="aminra-error">${kcSanitize(messagesPerField.get('username'))?no_esc}</span>
        </#if>
      </div>

      <button class="aminra-submit" type="submit">${msg("doSubmit")}</button>
    </form>

  <#elseif section="info">
    <p>${msg("emailInstruction")}</p>
    <p style="margin-top:12px;"><a href="${url.loginUrl}">${kcSanitize(msg("backToLogin"))?no_esc}</a></p>

  </#if>

</@layout.registrationLayout>
