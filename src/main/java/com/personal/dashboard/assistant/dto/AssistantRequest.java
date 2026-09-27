package com.personal.dashboard.assistant.dto;

import com.personal.dashboard.studio.dto.StudioDto;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** Home assistant input; execution target and privileges are selected by the server. */
public record AssistantRequest(
    @NotBlank @Size(max = 40) String action, @Valid StudioDto.Args args) {}
