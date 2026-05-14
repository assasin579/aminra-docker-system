<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>

  <#if section="header">
    <p class="aminra-subtitle">${msg("errorTitle")}</p>

  <#elseif section="form">
    <div class="alert alert-error">
      <#if message?? && message.summary?has_content>
        ${kcSanitize(message.summary)?no_esc}
      <#else>
        ${msg("errorTitleHtml")?no_esc}
      </#if>
    </div>

    <#if client?? && client.baseUrl?has_content>
      <p style="text-align:center; margin-top:16px;">
        <a class="aminra-link" id="backToApplication" href="${client.baseUrl}">${kcSanitize(msg("backToApplication"))?no_esc}</a>
      </p>
    </#if>

  </#if>

</@layout.registrationLayout>
