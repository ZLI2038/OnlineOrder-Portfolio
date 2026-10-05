package io.github.zli2038.onlineorder.model;

public record RegisterBody(
        String email,
        String password,
        String firstName,
        String lastName
) {
}
