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

  <#-- Locale switcher (dropdown with flag + name) -->
  <#if realm.internationalizationEnabled && locale.supported?size gt 1>
    <#assign flagMap = {"vi": "🇻🇳", "en": "🇬🇧", "ar": "🇸🇦", "fr": "🇫🇷", "zh-CN": "🇨🇳"}>
    <details class="aminra-locale" aria-label="Chọn ngôn ngữ">
      <summary>
        <#list locale.supported as l>
          <#if l.languageTag == locale.currentLanguageTag>
            <span class="flag">${(flagMap[l.languageTag])!"🌐"}</span>
            <span class="name">${l.label}</span>
          </#if>
        </#list>
        <svg class="chevron" width="10" height="6" viewBox="0 0 10 6" fill="none" aria-hidden="true">
          <path d="M1 1L5 5L9 1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </summary>
      <div class="aminra-locale-menu" role="menu">
        <#list locale.supported as l>
          <#if l.languageTag == locale.currentLanguageTag>
            <span class="aminra-locale-item active" role="menuitem" aria-current="true">
              <span class="flag">${(flagMap[l.languageTag])!"🌐"}</span>
              <span class="name">${l.label}</span>
              <svg class="check" width="12" height="10" viewBox="0 0 12 10" fill="none" aria-hidden="true">
                <path d="M1 5L4.5 8.5L11 1.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </span>
          <#else>
            <a class="aminra-locale-item" href="${l.url}" role="menuitem">
              <span class="flag">${(flagMap[l.languageTag])!"🌐"}</span>
              <span class="name">${l.label}</span>
            </a>
          </#if>
        </#list>
      </div>
    </details>
  </#if>

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
