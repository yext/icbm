package com.example.foo;

import com.example.bar.Bar;

public class Foo {
    public static void main(String[] args) {
        System.out.println("Hello, world, from Foo!");
        Bar.helloWorld();

        System.out.println();

        FooProtos.FooMsg msg = FooProtos.FooMsg.newBuilder()
            .setText("Hello, world, from FooProtos!")
            .build();
        System.out.println("A message from FooProtos:");
        System.out.println(msg);
    }
}
