<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html lang="${locale.currentLanguageTag}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${msg("loginTitle",(realm.displayName!''))}</title>
  <link rel="icon" href="${url.resourcesPath}/img/aminra-mark.png">
  <#if properties.styles?has_content>
    <#list properties.styles?split(' ') as style>
      <link href="${url.resourcesPath}/${style}" rel="stylesheet">
    </#list>
  </#if>
</head>
<body class="aminra-page ${bodyClass}">
  <div class="aminra-container">

    <#-- Logo block -->
    <div class="aminra-logo-block">
      <div class="aminra-mark-wrap">
        <img src="${url.resourcesPath}/img/aminra-mark.png" alt="AMINRA mark" class="aminra-mark">
      </div>
      <img src="${url.resourcesPath}/img/aminra-wordmark-navy.png" alt="AMINRA" class="aminra-wordmark">
      <#nested "header">
    </div>

    <#-- Card -->
    <div class="aminra-card">
      <#-- Display Keycloak feedback messages -->
      <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
        <div class="alert alert-${message.type}">
          <#if message.summary?contains('&lt;')>${kcSanitize(message.summary)?no_esc}<#else>${message.summary?no_esc}</#if>
        </div>
      </#if>

      <#nested "form">

      <#if displayInfo>
        <div class="aminra-card-footer">
          <#nested "info">
        </div>
      </#if>
    </div>

    <#nested "footer">
  </div>
</body>
</html>
</#macro>
