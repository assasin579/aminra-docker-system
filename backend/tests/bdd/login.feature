Feature: Business owner login
  As a business owner
  I want to log in with my registered credentials
  So that I can access my Halal certification dashboard

  Background:
    Given an active business owner "biz-demo-1@demo.aminra.vn" with password "DemoP@ss2026"

  Scenario: Successful login returns access token
    When the owner submits valid credentials to /auth/login
    Then the response status is 200
    And the response body has a non-empty access_token
    And the response body has a non-empty refresh_token

  Scenario: Wrong password returns 401
    When the owner submits the email but password "WrongPass!1"
    Then the response status is 401
    And the response body contains "Email hoặc mật khẩu không đúng"

  Scenario: Suspended account cannot log in
    Given the owner account status is "suspended"
    When the owner submits valid credentials to /auth/login
    Then the response status is 403
    And the response body contains "tạm khoá"
