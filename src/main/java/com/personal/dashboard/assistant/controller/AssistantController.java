package com.personal.dashboard.assistant.controller;

import com.personal.dashboard.assistant.dto.AssistantProject;
import com.personal.dashboard.assistant.dto.AssistantRequest;
import com.personal.dashboard.assistant.service.AssistantService;
import com.personal.dashboard.studio.dto.AssistantDto;
import com.personal.dashboard.studio.dto.StudioDto;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

/** Authenticated home assistant resources; browser writes retain the existing CSRF protection. */
@RestController
@RequestMapping("/api/v1/assistant")
public class AssistantController {
  private final AssistantService service;

  public AssistantController(AssistantService service) {
    this.service = service;
  }

  @GetMapping
  public AssistantProject project() {
    return service.project();
  }

  @PostMapping("/jobs")
  @ResponseStatus(HttpStatus.ACCEPTED)
  public StudioDto.JobView start(
      @Valid @RequestBody AssistantRequest input, HttpServletRequest request) {
    return service.start(
        request.getSession().getId(), request.getLocalPort(), request.getContextPath(), input);
  }

  @GetMapping("/jobs/{id}")
  public StudioDto.JobView get(@PathVariable String id, HttpServletRequest request) {
    return service.get(request.getSession().getId(), id);
  }

  @DeleteMapping("/jobs/{id}")
  @ResponseStatus(HttpStatus.NO_CONTENT)
  public void cancel(@PathVariable String id, HttpServletRequest request) {
    service.cancel(request.getSession().getId(), id);
  }

  @PostMapping("/jobs/{id}/inputs")
  @ResponseStatus(HttpStatus.NO_CONTENT)
  public void control(
      @PathVariable String id,
      @Valid @RequestBody AssistantDto.Control input,
      HttpServletRequest request) {
    service.control(request.getSession().getId(), id, input);
  }
}
