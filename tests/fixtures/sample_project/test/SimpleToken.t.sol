// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {SimpleToken} from "../src/SimpleToken.sol";

contract SimpleTokenTest is Test {
    SimpleToken token;
    address owner = address(1);
    address alice = address(2);

    function setUp() public {
        vm.prank(owner);
        token = new SimpleToken("Simple", "SIM", 1_000_000e18);
    }

    function test_InitialSupply() public view {
        assertEq(token.totalSupply(), 1_000_000e18);
        assertEq(token.balanceOf(owner), 1_000_000e18);
    }

    function test_Transfer() public {
        vm.prank(owner);
        token.transfer(alice, 100e18);
        assertEq(token.balanceOf(alice), 100e18);
    }

    function test_MintByOwner() public {
        vm.prank(owner);
        token.mint(alice, 50e18);
        assertEq(token.balanceOf(alice), 50e18);
    }
}
