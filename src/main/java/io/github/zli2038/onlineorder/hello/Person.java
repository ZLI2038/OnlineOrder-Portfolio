package io.github.zli2038.onlineorder.hello;

public record Person(
        String name,
        String company,
        Address homeAddress,
        Book favoriteBook
) {
}
