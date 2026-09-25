"use client";

import React, { useState } from "react";
import { formatMoney, Payment } from "@/lib/schemas/payments";
import { useDailyPaymentTotal, usePayments } from "@/hooks/use-payments";
import { PaymentCreateModal } from "@/components/payments/payment-create-modal";
import { PaymentDetailModal } from "@/components/payments/payment-detail-modal";
import { PaymentVoidModal } from "@/components/payments/payment-void-modal";
import { PaymentCorrectModal } from "@/components/payments/payment-correct-modal";

interface PaymentsViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
}

export function PaymentsView({ orgId, userRole = "owner", token }: PaymentsViewProps) {
  const [statusFilter, setStatusFilter] = useState<string | undefined>("all");
  const [channelFilter, setChannelFilter] = useState<string | undefined>("all");
  const [selectedPayment, setSelectedPayment] = useState<Payment | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isVoidOpen, setIsVoidOpen] = useState(false);
  const [isCorrectOpen, setIsCorrectOpen] = useState(false);

  const effectiveStatus = statusFilter === "all" ? undefined : statusFilter;
  const effectiveChannel = channelFilter === "all" ? undefined : channelFilter;

  const { data, isLoading, error, refetch } = usePayments(
    orgId,
    {
      status: effectiveStatus,
      channel: effectiveChannel,
      limit: 100,
      offset: 0,
    },
    token
  );

  const todayStr = new Date().toISOString().split("T")[0];
  const { data: dailyTotalData } = useDailyPaymentTotal(orgId, todayStr, token);

  const normalizedRole = userRole.toLowerCase();
  const isOwner = normalizedRole === "owner";
  const isManager = normalizedRole === "manager";
  const isStaff = normalizedRole === "staff";

  // Permission flags:
  // - payments:create -> Owner, Manager, Staff
  // - payments:correct -> Owner, Manager
  // - payments:void -> Owner only
  const canCreate = isOwner || isManager || isStaff;
  const canCorrect = isOwner || isManager;
  const canVoid = isOwner;

  const payments = data?.items || [];

  const handleOpenDetail = (payment: Payment) => {
    setSelectedPayment(payment);
    setIsDetailOpen(true);
  };

  const handleOpenVoid = (payment: Payment) => {
    setSelectedPayment(payment);
    setIsVoidOpen(true);
  };

  const handleOpenCorrect = (payment: Payment) => {
    setSelectedPayment(payment);
    setIsCorrectOpen(true);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-800 border-green-200";
      case "voided":
        return "bg-red-100 text-red-800 border-red-200";
      case "corrected":
        return "bg-amber-100 text-amber-800 border-amber-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const formatChannel = (ch: string) => {
    switch (ch) {
      case "cash":
        return "Cash";
      case "bank_transfer":
        return "Bank Transfer";
      case "cheque":
        return "Cheque";
      case "mobile_wallet":
        return "Mobile Wallet";
      default:
        return ch;
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Payments & Receipts
          </h1>
          <p className="text-sm text-gray-500">
            Record customer receipts, link sales orders, and manage payment lifecycles.
          </p>
        </div>

        {canCreate && (
          <button
            onClick={() => setIsCreateOpen(true)}
            className="inline-flex items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none"
          >
            Record Receipt
          </button>
        )}
      </div>

      {/* Staff Notice */}
      {isStaff && (
        <div className="rounded-md border border-amber-100 bg-amber-50 p-3 text-xs text-amber-800">
          <span className="font-semibold">Staff Permissions:</span> You have permission to record new payments and view receipt records. Voiding requires Owner authority and corrections require Manager authority.
        </div>
      )}

      {/* Daily Summary Card */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
              Today's Collections ({todayStr})
            </span>
            <div className="text-2xl font-bold text-gray-900 mt-0.5">
              {dailyTotalData
                ? formatMoney(dailyTotalData.total_minor, dailyTotalData.currency_code)
                : "Rs. 0.00"}
            </div>
          </div>
          <div className="text-xs text-gray-500">
            {dailyTotalData ? dailyTotalData.payment_count : 0} active receipt(s) collected today
          </div>
        </div>
      </div>

      {/* Filter Tabs & Channel Selector */}
      <div className="flex flex-col sm:flex-row gap-4 sm:items-center sm:justify-between border-b border-gray-200 pb-3">
        {/* Status Tabs */}
        <div className="flex gap-2">
          {(["all", "active", "voided", "corrected"] as const).map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                statusFilter === st
                  ? "bg-indigo-50 text-indigo-700 font-semibold"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {/* Channel Dropdown */}
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-gray-500">Channel:</label>
          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            className="rounded-md border border-gray-300 py-1 px-2 text-xs focus:border-indigo-500 focus:outline-none"
          >
            <option value="all">All Channels</option>
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank Transfer</option>
            <option value="cheque">Cheque</option>
            <option value="mobile_wallet">Mobile Wallet</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>

      {/* Payments Table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">
            Loading payments...
          </div>
        ) : error ? (
          <div className="p-8 text-center text-sm text-red-600">
            Failed to load payments: {error.message}
            <div className="mt-2">
              <button
                onClick={() => refetch()}
                className="text-xs text-indigo-600 underline font-medium"
              >
                Retry
              </button>
            </div>
          </div>
        ) : payments.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-500">
            No payments found. {canCreate && "Click 'Record Receipt' to log your first payment."}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Receipt #</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Channel</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Date</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">Amount</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {payments.map((payment) => (
                  <tr key={payment.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900 font-mono">
                      {payment.payment_number}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      <div className="font-medium text-xs text-gray-900">
                        {formatChannel(payment.channel)}
                      </div>
                      {payment.account_label && (
                        <div className="text-[11px] text-gray-400">
                          {payment.account_label}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold capitalize ${getStatusBadge(
                          payment.status
                        )}`}
                      >
                        {payment.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {new Date(payment.received_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-gray-900">
                      {formatMoney(payment.amount_minor, payment.currency_code)}
                    </td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button
                        onClick={() => handleOpenDetail(payment)}
                        className="text-xs text-indigo-600 hover:text-indigo-900 font-medium"
                      >
                        View
                      </button>

                      {payment.status === "active" && canCorrect && (
                        <button
                          onClick={() => handleOpenCorrect(payment)}
                          className="text-xs text-amber-600 hover:text-amber-900 font-medium"
                        >
                          Correct
                        </button>
                      )}

                      {payment.status === "active" && canVoid && (
                        <button
                          onClick={() => handleOpenVoid(payment)}
                          className="text-xs text-red-600 hover:text-red-900 font-medium"
                        >
                          Void
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      <PaymentCreateModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        orgId={orgId}
        token={token}
      />

      <PaymentDetailModal
        isOpen={isDetailOpen}
        onClose={() => {
          setIsDetailOpen(false);
          setSelectedPayment(null);
        }}
        payment={selectedPayment}
      />

      <PaymentVoidModal
        isOpen={isVoidOpen}
        onClose={() => {
          setIsVoidOpen(false);
          setSelectedPayment(null);
        }}
        payment={selectedPayment}
        orgId={orgId}
        token={token}
      />

      <PaymentCorrectModal
        isOpen={isCorrectOpen}
        onClose={() => {
          setIsCorrectOpen(false);
          setSelectedPayment(null);
        }}
        payment={selectedPayment}
        orgId={orgId}
        token={token}
      />
    </div>
  );
}
